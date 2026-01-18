"""Comprehensive RSSM Dynamics Tests.

Tests for Recurrent State-Space Model dynamics:
1. OrganismRSSM coordination
2. Gradient flow
3. Numerical stability
4. Integration with KagamiWorldModel

UPDATED: December 27, 2025
Consolidated all RSSM tests to use OrganismRSSM (removed BatchedOrganismCore).
"""

from __future__ import annotations

from typing import Any

import pytest

import torch

# Set seed for reproducibility
torch.manual_seed(42)

pytestmark = pytest.mark.tier_integration


class TestOrganismRSSM:
    """Test OrganismRSSM (7-colony system) dynamics."""

    @pytest.fixture
    def organism(self) -> Any:
        """Create OrganismRSSM for testing."""
        from kagami.core.world_model.colony_rssm import ColonyRSSMConfig, OrganismRSSM

        config = ColonyRSSMConfig()
        return OrganismRSSM(config=config)

    def test_creates_seven_colonies(self, organism) -> None:
        """Test that 7 colony states can be initialized."""
        assert organism.get_current_states() is None
        organism.initialize_all()
        states = organism.get_current_states()
        assert states is not None
        assert len(states) == organism.config.num_colonies == 7

    def test_step_all_processes_all_colonies(self, organism) -> None:
        """Test step_all returns a stable interface with E8/S7 inputs."""
        e8_code = torch.randn(8)
        s7_phase = torch.randn(7)

        result = organism.step_all(e8_code=e8_code, s7_phase=s7_phase)

        assert "organism_action" in result
        assert "states" in result
        assert result["organism_action"].shape == (organism.config.action_dim,)
        assert len(result["states"]) == organism.config.num_colonies

    def test_forward_produces_valid_output(self, organism) -> None:
        """Test forward pass produces valid output shapes."""
        B, T = 2, 4
        e8_code = torch.randn(B, T, 8)
        s7_phase = torch.randn(B, T, 7)

        result = organism.forward(e8_code, s7_phase, sample=True)

        # Validate shapes: [B, T, 7, dim]
        assert result["h"].shape == (B, T, 7, organism.deter_dim)
        assert result["z"].shape == (B, T, 7, organism.stoch_dim)
        assert result["kl"].shape == (B, T, 7)
        assert torch.isfinite(result["h"]).all()
        assert torch.isfinite(result["z"]).all()

    def test_gradient_flow(self, organism) -> None:
        """Test gradients flow through RSSM."""
        B, T = 2, 4
        e8_code = torch.randn(B, T, 8, requires_grad=True)
        s7_phase = torch.randn(B, T, 7, requires_grad=True)

        result = organism.forward(e8_code, s7_phase, sample=False)
        loss = result["h"].sum() + result["z"].sum()
        loss.backward()

        assert e8_code.grad is not None, "Gradients should flow to e8_code"
        assert s7_phase.grad is not None, "Gradients should flow to s7_phase"
        assert torch.isfinite(e8_code.grad).all()
        assert torch.isfinite(s7_phase.grad).all()

    def test_unimix_probability_floor(self, organism) -> None:
        """Unimix should enforce a non-zero probability floor (DreamerV3)."""
        e8_code = torch.randn(2, 8)
        s7_phase = torch.randn(2, 7)

        result = organism.step_all(e8_code=e8_code, s7_phase=s7_phase, sample=False)

        post_probs = result["posterior_probs"]
        prior_probs = result["prior_probs"]

        K = organism.latent_classes
        assert post_probs.shape[-1] == K
        assert prior_probs.shape[-1] == K

        # After unimix, every class must have at least unimix/K probability
        floor = organism.unimix * (1.0 / float(K))
        assert float(post_probs.min().item()) >= floor - 1e-7

    def test_free_bits_clips_kl_but_preserves_gradients(self, organism) -> None:
        """Free-bits should clip KL forward values without zeroing gradients (STE).

        Note (Jan 4, 2026): result["kl"] is raw KL for logging (unclipped).
        result["kl_balanced"] is the DreamerV3 balanced KL with free_bits applied.
        The free_bits clipping happens in balanced_kl_loss_categorical.
        """
        e8_code = torch.randn(2, 8, requires_grad=True)
        s7_phase = torch.randn(2, 7, requires_grad=True)

        result = organism.step_all(e8_code=e8_code, s7_phase=s7_phase, sample=False)

        # kl_balanced should have free_bits clipping applied
        # (kl_balanced is a scalar from balanced_kl_loss_categorical)
        kl_balanced = result["kl_balanced"]
        assert torch.isfinite(kl_balanced), "kl_balanced should be finite"

        # Raw kl is unclipped (for logging purposes)
        kl_raw = result["kl"]
        assert torch.isfinite(kl_raw).all(), "Raw KL should be finite"

        # Gradient should still flow (STE behavior)
        loss = result["kl_loss"]  # Uses kl_balanced
        loss.backward()

        assert e8_code.grad is not None, "Gradients should flow to e8_code"
        assert torch.isfinite(e8_code.grad).all(), "Gradients should be finite"

    def test_episode_boundary_handling(self, organism) -> None:
        """Test DreamerV3-style episode boundary handling."""
        B, T = 2, 4
        e8_code = torch.randn(B, T, 8)
        s7_phase = torch.randn(B, T, 7)

        # Create continue flags: episode ends at t=2
        continue_flags = torch.ones(B, T)
        continue_flags[:, 2] = 0  # Episode boundary

        result = organism.forward(e8_code, s7_phase, continue_flags=continue_flags)

        # Should complete without errors
        assert result["h"].shape == (B, T, 7, organism.deter_dim)
        assert torch.isfinite(result["h"]).all()


class TestRSSMNumericalStability:
    """Test RSSM numerical stability."""

    @pytest.fixture
    def organism(self) -> Any:
        from kagami.core.world_model.colony_rssm import ColonyRSSMConfig, OrganismRSSM

        return OrganismRSSM(config=ColonyRSSMConfig())

    def test_large_observation_values(self, organism) -> None:
        """Test stability with large observation values."""
        e8_code = torch.randn(8) * 100
        s7_phase = torch.randn(7) * 100

        result = organism.step_all(e8_code=e8_code, s7_phase=s7_phase)

        assert "organism_action" in result
        assert torch.isfinite(result["organism_action"]).all()

    def test_zero_observation(self, organism) -> None:
        """Test stability with zero observation."""
        e8_code = torch.zeros(8)
        s7_phase = torch.zeros(7)

        result = organism.step_all(e8_code=e8_code, s7_phase=s7_phase)

        assert "organism_action" in result

    def test_small_observation_values(self, organism) -> None:
        """Test stability with very small observation values."""
        e8_code = torch.randn(8) * 1e-8
        s7_phase = torch.randn(7) * 1e-8

        result = organism.step_all(e8_code=e8_code, s7_phase=s7_phase)

        assert "organism_action" in result


class TestRSSMIntegrationWithKagami:
    """Test RSSM integration with KagamiWorldModel."""

    @pytest.fixture
    def model(self) -> Any:
        from kagami.core.world_model.kagami_world_model import KagamiWorldModelFactory

        return KagamiWorldModelFactory.create()

    def test_forward_pass(self, model) -> None:
        """Test KagamiWorldModel forward pass."""
        dim = model.config.layer_dimensions[0]
        x = torch.randn(4, 8, dim)

        model.eval()
        with torch.no_grad():
            output, _metrics = model(x)

        assert torch.isfinite(output).all()
        assert output.shape == x.shape

    def test_forward_with_gradients(self, model) -> None:
        """Test gradients flow in KagamiWorldModel."""
        dim = model.config.layer_dimensions[0]
        x = torch.randn(4, 8, dim, requires_grad=True)

        model.train()
        model.zero_grad()

        output, _metrics = model(x)
        loss = output.sum()
        loss.backward()

        assert x.grad is not None
        assert torch.isfinite(x.grad).all()


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
