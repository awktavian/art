"""Markov-blanket gradient tests.

Validates differentiable contracts for OrganismRSSM:
- Gradients flow from S7 phase through RSSM dynamics
- OrganismRSSM.step_all() exposes a stable interface
- Gradient flow is preserved across all components

UPDATED (December 27, 2025):
============================
Migrated from BatchedOrganismCore (removed) to OrganismRSSM.
All RSSM functionality is now consolidated in OrganismRSSM.
"""

from __future__ import annotations

import pytest

import torch

from kagami.core.world_model.colony_rssm import (
    ColonyRSSMConfig,
    OrganismRSSM,
)

pytestmark = pytest.mark.tier_integration


class TestOrganismRSSMGradients:
    """Test gradient flow through the differentiable RSSM."""

    def test_rssm_e8_to_outputs_has_gradients(self) -> None:
        """Test gradients flow from E8/S7 inputs through RSSM outputs."""
        config = ColonyRSSMConfig()
        rssm = OrganismRSSM(config=config)

        # E8 code [B, 8] and S7 phase [B, 7]
        e8_code = torch.randn(2, 8, requires_grad=True)
        s7_phase = torch.randn(2, 7, requires_grad=True)

        result = rssm.step_all(e8_code=e8_code, s7_phase=s7_phase, sample=False)

        # Compute loss from outputs
        h_next = result["h_next"]  # [B, 7, H]
        z_next = result["z_next"]  # [B, 7, Z]
        loss = h_next.sum() + z_next.sum()
        loss.backward()

        assert e8_code.grad is not None, "Gradients should flow to e8_code"
        assert s7_phase.grad is not None, "Gradients should flow to s7_phase"
        assert torch.isfinite(e8_code.grad).all(), "e8_code gradients should be finite"
        assert torch.isfinite(s7_phase.grad).all(), "s7_phase gradients should be finite"

    def test_step_all_returns_organism_action(self) -> None:
        """OrganismRSSM.step_all() exposes a stable interface."""
        rssm = OrganismRSSM(config=ColonyRSSMConfig())

        # E8 code [8] and S7 phase [7] (unbatched)
        e8_code = torch.randn(8)
        s7_phase = torch.randn(7)
        result = rssm.step_all(e8_code=e8_code, s7_phase=s7_phase)

        assert "organism_action" in result, "step_all should return organism_action"
        assert result["organism_action"].shape == (rssm.config.action_dim,)

    def test_kl_gradient_flow(self) -> None:
        """Test gradients flow through KL divergence computation."""
        config = ColonyRSSMConfig()
        rssm = OrganismRSSM(config=config)

        e8_code = torch.randn(2, 8, requires_grad=True)
        s7_phase = torch.randn(2, 7, requires_grad=True)

        result = rssm.step_all(e8_code=e8_code, s7_phase=s7_phase, sample=False)

        # KL loss should have gradients
        kl_loss = result["kl_loss"]
        kl_loss.backward()

        assert e8_code.grad is not None, "KL gradients should flow to e8_code"
        assert s7_phase.grad is not None, "KL gradients should flow to s7_phase"


class TestRSSMStability:
    """Stability checks for RSSM."""

    def test_repeated_calls_stable(self) -> None:
        """step_all is stable across repeated calls."""
        rssm = OrganismRSSM(config=ColonyRSSMConfig())
        e8_code = torch.randn(8)
        s7_phase = torch.randn(7)

        result1 = rssm.step_all(e8_code=e8_code, s7_phase=s7_phase)
        result2 = rssm.step_all(e8_code=e8_code, s7_phase=s7_phase)

        assert result1.keys() == result2.keys()

    def test_forward_sequence_gradient_flow(self) -> None:
        """Test gradients flow through sequence forward."""
        config = ColonyRSSMConfig()
        rssm = OrganismRSSM(config=config)

        # Sequence inputs
        B, T = 2, 4
        e8_code = torch.randn(B, T, 8, requires_grad=True)
        s7_phase = torch.randn(B, T, 7, requires_grad=True)

        result = rssm.forward(e8_code, s7_phase, sample=False)

        loss = result["h"].sum() + result["z"].sum()
        loss.backward()

        assert e8_code.grad is not None, "Sequence gradients should flow"
        assert torch.isfinite(e8_code.grad).all()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
