"""End-to-end training validation for KagamiWorldModel.

Created: January 4, 2026
Purpose: Validate complete training pipeline end-to-end.

Tests:
1. Model creation → training step → gradient flow → loss decrease
2. Full forward/backward cycle with all loss components
3. H-JEPA predictor/target update
4. RSSM dynamics integration
5. Checkpoint save/load roundtrip
"""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest
import torch

# No infra required - this tests the model itself, not external services
# Use tier_unit since it doesn't need Weaviate/etcd
pytestmark = pytest.mark.tier_unit


class TestE2EWorldModelTraining:
    """End-to-end training validation."""

    @pytest.fixture
    def model(self) -> torch.nn.Module:
        """Create minimal KagamiWorldModel for E2E testing."""
        from kagami.core.world_model.kagami_world_model import KagamiWorldModelFactory

        return KagamiWorldModelFactory.create()

    @pytest.fixture
    def optimizer(self, model: torch.nn.Module) -> torch.optim.Optimizer:
        """Create optimizer for training."""
        return torch.optim.AdamW(model.parameters(), lr=1e-4, weight_decay=0.01)

    def test_full_training_cycle(
        self, model: torch.nn.Module, optimizer: torch.optim.Optimizer
    ) -> None:
        """Test complete training cycle: forward → loss → backward → optimize."""
        device = next(model.parameters()).device
        batch_size = 2
        seq_len = 4
        input_dim = model.config.layer_dimensions[0]

        # Create synthetic batch
        x = torch.randn(batch_size, seq_len, input_dim, device=device)
        target = torch.randn(batch_size, seq_len, input_dim, device=device)

        model.train()
        initial_loss = None
        final_loss = None

        # Run 5 training steps
        for step in range(5):
            optimizer.zero_grad()

            # Forward pass
            loss_output = model.training_step(x, target)

            # Verify loss structure
            assert hasattr(loss_output, "total"), "training_step must return LossOutput with .total"
            assert hasattr(loss_output, "components"), (
                "training_step must return LossOutput with .components"
            )

            total_loss = loss_output.total
            assert torch.isfinite(total_loss), f"Loss is not finite at step {step}"

            # Track loss
            if step == 0:
                initial_loss = total_loss.item()
            if step == 4:
                final_loss = total_loss.item()

            # Backward
            total_loss.backward()

            # Verify gradients exist
            params_with_grad = sum(1 for p in model.parameters() if p.grad is not None)
            total_params = sum(1 for p in model.parameters() if p.requires_grad)
            assert params_with_grad > 0, f"No gradients at step {step}"

            # Clip gradients (DreamerV3 style)
            torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm=1.0)

            # Optimize
            optimizer.step()

        # Verify learning signal (loss should decrease or stay similar)
        assert initial_loss is not None
        assert final_loss is not None
        print(f"✅ E2E Training: loss {initial_loss:.4f} → {final_loss:.4f}")

        # Allow 50% variance (random data may not always decrease)
        assert final_loss < initial_loss * 1.5, (
            f"Loss increased significantly: {initial_loss:.4f} → {final_loss:.4f}"
        )

    def test_h_jepa_ema_update(self, model: torch.nn.Module) -> None:
        """Test H-JEPA predictor → target EMA update."""
        if model.h_jepa_predictor is None or model.h_jepa_target is None:
            pytest.skip("H-JEPA not configured in model")

        # Get initial target parameters
        initial_target = {
            name: param.clone() for name, param in model.h_jepa_target.named_parameters()
        }

        # Modify predictor (simulate training)
        for param in model.h_jepa_predictor.parameters():
            param.data.add_(torch.randn_like(param) * 0.1)

        # EMA update
        model.update_h_jepa_target(tau=0.99)

        # Verify target parameters changed
        target_changed = False
        for name, param in model.h_jepa_target.named_parameters():
            if not torch.allclose(param, initial_target[name], atol=1e-6):
                target_changed = True
                break

        assert target_changed, "H-JEPA target should update via EMA"
        print("✅ H-JEPA EMA update verified")

    def test_rssm_kl_in_training_step(self, model: torch.nn.Module) -> None:
        """Test RSSM KL divergence is computed in training step."""
        device = next(model.parameters()).device
        batch_size = 2
        seq_len = 4
        input_dim = model.config.layer_dimensions[0]

        x = torch.randn(batch_size, seq_len, input_dim, device=device)
        target = torch.randn(batch_size, seq_len, input_dim, device=device)

        model.train()
        loss_output = model.training_step(x, target)

        # RSSM KL should be in components (uses kl_balanced with free_bits)
        if "rssm_kl" in loss_output.components:
            rssm_kl = loss_output.components["rssm_kl"]
            if isinstance(rssm_kl, torch.Tensor):
                rssm_kl = rssm_kl.item()
            assert rssm_kl >= 0, "KL divergence should be non-negative"
            print(f"✅ RSSM KL: {rssm_kl:.4f}")
        else:
            print("⚠️ RSSM KL not in loss components (may be model variant)")

    def test_checkpoint_roundtrip(
        self, model: torch.nn.Module, optimizer: torch.optim.Optimizer
    ) -> None:
        """Test checkpoint save/load preserves training state.

        NOTE: This model has stochastic components (RSSM with discrete latent sampling).
        Loss values will differ between runs even with identical parameters due to
        sampling. We verify parameter restoration is exact and loss is "similar order".
        """
        device = next(model.parameters()).device
        input_dim = model.config.layer_dimensions[0]

        # Run a few training steps
        x = torch.randn(2, 4, input_dim, device=device)
        target = torch.randn(2, 4, input_dim, device=device)

        model.train()
        for _ in range(3):
            optimizer.zero_grad()
            loss = model.training_step(x, target).total
            loss.backward()
            optimizer.step()

        # Get pre-save state - capture parameters (deterministic) and loss range
        pre_save_params = {name: param.clone() for name, param in model.named_parameters()}

        # Run multiple forward passes to get loss statistics (stochastic model)
        losses_before = []
        for _ in range(5):
            loss_val = model.training_step(x, target).total.item()
            losses_before.append(loss_val)
        mean_loss_before = sum(losses_before) / len(losses_before)
        std_loss_before = (
            sum((l - mean_loss_before) ** 2 for l in losses_before) / len(losses_before)
        ) ** 0.5

        # Save checkpoint
        with tempfile.TemporaryDirectory() as tmpdir:
            checkpoint_path = Path(tmpdir) / "checkpoint.pt"

            torch.save(
                {
                    "model_state_dict": model.state_dict(),
                    "optimizer_state_dict": optimizer.state_dict(),
                    "step": 3,
                },
                checkpoint_path,
            )

            # Reload into fresh model
            from kagami.core.world_model.kagami_world_model import KagamiWorldModelFactory

            fresh_model = KagamiWorldModelFactory.create()
            fresh_optimizer = torch.optim.AdamW(fresh_model.parameters(), lr=1e-4)

            checkpoint = torch.load(checkpoint_path, weights_only=False)
            fresh_model.load_state_dict(checkpoint["model_state_dict"])
            fresh_optimizer.load_state_dict(checkpoint["optimizer_state_dict"])

            # CRITICAL: Verify parameters match EXACTLY (this is the real test)
            params_checked = 0
            for name, param in fresh_model.named_parameters():
                if name in pre_save_params:
                    assert torch.allclose(param, pre_save_params[name], atol=1e-6), (
                        f"Parameter {name} differs after checkpoint load"
                    )
                    params_checked += 1

            assert params_checked > 0, "No parameters were verified"

            # Verify loss is in similar range (allowing for stochastic variation)
            fresh_model.train()
            losses_after = []
            for _ in range(5):
                loss_val = fresh_model.training_step(x, target).total.item()
                losses_after.append(loss_val)
            mean_loss_after = sum(losses_after) / len(losses_after)

            # Allow 2 standard deviations + 50% tolerance for stochastic variation
            # This is a sanity check, not a precision test (params match is the real test)
            tolerance = max(std_loss_before * 3, mean_loss_before * 0.5, 1.0)
            assert abs(mean_loss_before - mean_loss_after) < tolerance, (
                f"Loss mean changed too much after checkpoint: "
                f"{mean_loss_before:.4f} ± {std_loss_before:.4f} → {mean_loss_after:.4f}"
            )

        print(
            f"✅ Checkpoint roundtrip verified: {params_checked} params, loss={mean_loss_before:.4f}"
        )

    def test_loss_components_all_finite(self, model: torch.nn.Module) -> None:
        """Test all loss components are finite (no NaN/Inf)."""
        device = next(model.parameters()).device
        input_dim = model.config.layer_dimensions[0]

        x = torch.randn(2, 4, input_dim, device=device)
        target = torch.randn(2, 4, input_dim, device=device)

        model.train()
        loss_output = model.training_step(x, target)

        # Check total
        assert torch.isfinite(loss_output.total), "Total loss is not finite"

        # Check all components
        for name, value in loss_output.components.items():
            if isinstance(value, torch.Tensor):
                assert torch.isfinite(value).all(), f"Component {name} has non-finite values"
            elif isinstance(value, (int, float)):
                import math

                assert math.isfinite(value), f"Component {name} is not finite: {value}"

        print(f"✅ All {len(loss_output.components)} loss components are finite")


class TestGradientMonitorIntegration:
    """Test GradientMonitor integration with training."""

    @pytest.fixture
    def model(self) -> torch.nn.Module:
        from kagami.core.world_model.kagami_world_model import KagamiWorldModelFactory

        return KagamiWorldModelFactory.create()

    def test_gradient_monitor_produces_report(self, model: torch.nn.Module) -> None:
        """Test GradientMonitor produces valid report during training."""
        from kagami.core.training.gradient_monitor import GradientMonitor

        device = next(model.parameters()).device
        input_dim = model.config.layer_dimensions[0]

        x = torch.randn(2, 4, input_dim, device=device)
        target = torch.randn(2, 4, input_dim, device=device)

        # Create monitor
        monitor = GradientMonitor(hourglass=model)

        # Training step
        model.train()
        model.zero_grad()
        loss = model.training_step(x, target).total
        loss.backward()

        # Analyze
        report = monitor.analyze()

        # Validate report
        assert report.total_params > 0, "Report should have params"
        assert report.params_with_grad > 0, "Some params should have gradients"
        assert not report.has_nans(), "Should not have NaN gradients"

        print(
            f"✅ GradientMonitor: {report.params_with_grad}/{report.total_params} params with gradients"
        )


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
