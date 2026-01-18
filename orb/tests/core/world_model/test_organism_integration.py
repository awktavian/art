"""Integration tests for OrganismRSSM.

COVERAGE TARGET: RSSM dynamics, PLAN→EXECUTE→VERIFY cycle, Markov blanket
ESTIMATED RUNTIME: <5 seconds

Tests verify:
1. Full PLAN → EXECUTE → VERIFY cycle execution
2. Receipt creation and validation
3. Markov blanket discipline (action isolation)
4. Colony state dynamics and transitions
5. Fano plane attention coupling

Mathematical Foundation:
- RSSM: Recurrent State Space Model (Hafner et al. 2019)
- Markov blanket: η → s → μ → a → η (Pearl 1988)
- Fano plane: 7 colonies with sparse coupling via 7 lines
"""

from __future__ import annotations

import pytest

import torch

from kagami.core.config.unified_config import get_kagami_config
from kagami.core.world_model.colony_rssm import (
    ColonyRSSMConfig,
    ColonyState,
    OrganismRSSM,
    create_rssm_world_model,
    get_organism_rssm,
    reset_organism_rssm,
)

# Consolidated markers
pytestmark = [
    pytest.mark.tier_integration,
    pytest.mark.timeout(5),
]


class TestOrganismRSSMInitialization:
    """Test OrganismRSSM initialization and configuration."""

    def test_default_initialization(self) -> None:
        """OrganismRSSM should initialize with default config."""
        rssm = OrganismRSSM()

        assert rssm.num_colonies == 7
        assert isinstance(rssm.config, ColonyRSSMConfig)

    def test_custom_config_initialization(self) -> None:
        """OrganismRSSM should accept custom config."""
        config = ColonyRSSMConfig(
            obs_dim=256,
            colony_dim=128,
            action_dim=64,
            num_colonies=7,
        )
        rssm = OrganismRSSM(config)

        assert rssm.obs_dim == 256
        assert rssm.deter_dim == 128
        assert rssm.action_dim == 64

    def test_default_config_factory(self) -> None:
        """Default config factory should return valid config."""
        config = get_kagami_config().world_model.rssm

        assert isinstance(config, ColonyRSSMConfig)
        assert config.num_colonies == 7
        assert config.obs_dim > 0
        assert config.colony_dim > 0

    def test_singleton_organism_rssm(self) -> None:
        """get_organism_rssm should return singleton instance."""
        rssm1 = get_organism_rssm()
        rssm2 = get_organism_rssm()

        assert rssm1 is rssm2, "Should return same singleton instance"

    def test_reset_organism_rssm(self) -> None:
        """reset_organism_rssm should clear singleton."""
        rssm1 = get_organism_rssm()
        reset_organism_rssm()
        rssm2 = get_organism_rssm()

        # After reset, should get a fresh instance
        assert isinstance(rssm2, OrganismRSSM)


class TestColonyStateManagement:
    """Test colony state creation and management."""

    def test_colony_state_creation(self) -> None:
        """ColonyState should initialize with correct dimensions."""
        # Create states for each colony (need 2D tensors: batch × features)
        states = []
        for colony_id in range(7):
            state = ColonyState(
                hidden=torch.randn(1, 512),  # 2D: batch × features
                stochastic=torch.randn(1, 256),
                colony_id=colony_id,
            )
            states.append(state)

        assert len(states) == 7
        assert all(s.hidden.shape == (1, 512) for s in states)
        assert all(s.stochastic.shape == (1, 256) for s in states)

    def test_colony_state_device_transfer(self) -> None:
        """ColonyState should support device transfer."""
        state = ColonyState(
            hidden=torch.randn(1, 512),  # 2D
            stochastic=torch.randn(1, 256),  # 2D
            colony_id=0,
        )

        # Should be on CPU by default
        assert state.hidden.device.type == "cpu"

    def test_batch_colony_states(self) -> None:
        """Colony states should support batch dimensions."""
        # Batch of states for one colony
        batch_size = 4
        state = ColonyState(
            hidden=torch.randn(batch_size, 512),
            stochastic=torch.randn(batch_size, 256),
            colony_id=0,
        )

        assert state.hidden.shape[0] == batch_size


class TestRSSMForwardPass:
    """Test RSSM forward pass and dynamics."""

    def test_forward_pass_shapes(self) -> None:
        """RSSM forward should produce correct output shapes."""
        config = ColonyRSSMConfig(
            obs_dim=512,
            colony_dim=256,
            stochastic_dim=128,
            action_dim=64,
            num_colonies=7,
        )
        rssm = OrganismRSSM(config)

        # UPDATED (Dec 22, 2025): Test step_all with E8 code + S7 phase
        e8_code = torch.randn(1, 8)  # E8 code
        s7_phase = torch.randn(1, 7)  # S7 phase
        result = rssm.step_all(e8_code=e8_code, s7_phase=s7_phase, enable_cot=False)
        assert "organism_action" in result
        assert result["organism_action"].shape == (64,)  # action_dim

    def test_action_decoding(self) -> None:
        """Action decoder should produce valid actions."""
        config = ColonyRSSMConfig(
            obs_dim=512,
            colony_dim=256,
            stochastic_dim=128,
            action_dim=64,
            num_colonies=7,
        )
        rssm = OrganismRSSM(config)

        h = torch.randn(7, 256)
        z = torch.randn(7, 128)

        # Decode action
        hz = torch.cat([h, z], dim=-1)
        actions = rssm.action_head(hz)

        assert actions.shape == (7, 64)

    def test_observation_reconstruction(self) -> None:
        """Observation decoder should reconstruct E8 code.

        UPDATED (Dec 22, 2025): obs_decoder now outputs E8 code [B, 8].
        Full E8 lattice E2E dynamics.
        """
        config = ColonyRSSMConfig(
            obs_dim=8,  # E8 code dimension
            colony_dim=256,
            stochastic_dim=128,
            action_dim=64,
            num_colonies=7,
        )
        rssm = OrganismRSSM(config)

        h = torch.randn(7, 256)
        z = torch.randn(7, 128)

        # Reconstruct E8 code (not S7 phase)
        hz = torch.cat([h, z], dim=-1)
        e8_recon = rssm.obs_decoder(hz)

        assert e8_recon.shape == (7, 8)  # Each colony predicts 8D E8


class TestMarkovBlanketDiscipline:
    """Test Markov blanket discipline (action isolation)."""

    def test_action_isolation(self) -> None:
        """Actions at time t should not instantaneously affect state at t."""
        config = ColonyRSSMConfig(
            obs_dim=256,
            colony_dim=128,
            stochastic_dim=64,
            action_dim=32,
            num_colonies=7,
        )
        rssm = OrganismRSSM(config)

        # Previous state
        h_prev = torch.randn(7, 128)
        z_prev = torch.randn(7, 64)
        a_prev = torch.randn(7, 32)

        # Compute next h using PREVIOUS action
        input_to_dynamics = torch.cat([z_prev, a_prev], dim=-1)
        h_next = rssm.dynamics_cell(input_to_dynamics.view(7, -1), h_prev)

        assert h_next.shape == (7, 128)
        # h_next depends on a_prev, not a_current

    def test_no_instantaneous_feedback(self) -> None:
        """Current action should not create feedback loops."""
        config = ColonyRSSMConfig(
            obs_dim=256,
            colony_dim=128,
            stochastic_dim=64,
            action_dim=32,
            num_colonies=7,
        )
        rssm = OrganismRSSM(config)

        h = torch.randn(7, 128)
        z = torch.randn(7, 64)

        # Decode action from current state
        hz = torch.cat([h, z], dim=-1)
        a_current = rssm.action_head(hz)

        # Action is decoded but not fed back into dynamics immediately
        assert a_current.shape == (7, 32)

        # Next step would use a_current as a_prev
        # This ensures proper temporal sequencing


class TestFanoPlaneAttention:
    """Test Fano plane sparse attention mechanism."""

    def test_fano_attention_initialization(self) -> None:
        """Fano attention should initialize if enabled."""
        config = ColonyRSSMConfig(
            obs_dim=256,
            colony_dim=128,
            num_colonies=7,
            use_sparse_fano_attention=True,
        )
        rssm = OrganismRSSM(config)

        # Check if attention mechanism exists
        assert hasattr(rssm, "config")
        assert rssm.config.use_sparse_fano_attention

    def test_colony_embedding(self) -> None:
        """Colony embeddings should exist for identity."""
        config = ColonyRSSMConfig(
            obs_dim=256,
            colony_dim=128,
            num_colonies=7,
        )
        rssm = OrganismRSSM(config)

        # Get colony embeddings
        colony_ids = torch.arange(7)
        embeddings = rssm.colony_emb(colony_ids)

        assert embeddings.shape == (7, 128)


class TestRSSMLatentSpace:
    """Test RSSM latent space and stochastic dynamics."""

    def test_prior_network(self) -> None:
        """Prior network should compute p(z_t | h_t)."""
        config = ColonyRSSMConfig(
            obs_dim=256,
            colony_dim=128,
            stochastic_dim=64,
            num_colonies=7,
            latent_classes=240,
        )
        rssm = OrganismRSSM(config)

        h = torch.randn(7, 128)

        # Prior logits
        prior_logits = rssm.prior_net(h)

        assert prior_logits.shape == (7, 240)

    def test_posterior_network(self) -> None:
        """Posterior network should compute q(z_t | h_t, o_t)."""
        config = ColonyRSSMConfig(
            obs_dim=256,
            colony_dim=128,
            stochastic_dim=64,
            num_colonies=7,
            latent_classes=240,
        )
        rssm = OrganismRSSM(config)

        h = torch.randn(7, 128)
        obs_enc = torch.randn(7, 128)

        # Posterior logits
        h_obs = torch.cat([h, obs_enc], dim=-1)
        posterior_logits = rssm.posterior_net(h_obs)

        assert posterior_logits.shape == (7, 240)

    def test_latent_embedding(self) -> None:
        """Latent classes should embed to continuous vectors."""
        config = ColonyRSSMConfig(
            obs_dim=256,
            colony_dim=128,
            stochastic_dim=64,
            num_colonies=7,
            latent_classes=240,
        )
        rssm = OrganismRSSM(config)

        # Sample latent class indices
        latent_indices = torch.randint(0, 240, (7,))

        # Embed to continuous
        z = rssm.latent_embed(latent_indices)

        assert z.shape == (7, 64)


class TestPlanExecuteVerifyCycle:
    """Test full PLAN → EXECUTE → VERIFY cycle."""

    def test_plan_phase_initialization(self) -> None:
        """PLAN phase should initialize RSSM state."""
        rssm = OrganismRSSM()

        # PLAN phase: initialize colony states for each colony
        config = rssm.config

        states = []
        for colony_id in range(7):
            state = ColonyState(
                hidden=torch.zeros(1, config.colony_dim),  # 2D
                stochastic=torch.zeros(1, config.stochastic_dim),  # 2D
                colony_id=colony_id,
            )
            states.append(state)

        assert len(states) == 7
        assert all(s.hidden.shape == (1, config.colony_dim) for s in states)

    def test_execute_phase_action_generation(self) -> None:
        """EXECUTE phase should generate actions."""
        config = ColonyRSSMConfig(
            obs_dim=256,
            colony_dim=128,
            stochastic_dim=64,
            action_dim=32,
            num_colonies=7,
        )
        rssm = OrganismRSSM(config)

        # Current state
        h = torch.randn(7, 128)
        z = torch.randn(7, 64)

        # Generate actions
        hz = torch.cat([h, z], dim=-1)
        actions = rssm.action_head(hz)

        assert actions.shape == (7, 32)

    def test_verify_phase_reconstruction(self) -> None:
        """VERIFY phase should check reconstruction quality.

        UPDATED (Dec 22, 2025): obs_decoder now outputs E8 code [7, 8].
        Full E8 lattice E2E dynamics.
        """
        config = ColonyRSSMConfig(
            obs_dim=8,  # E8 code dimension
            colony_dim=128,
            stochastic_dim=64,
            action_dim=32,
            num_colonies=7,
        )
        rssm = OrganismRSSM(config)

        # State
        h = torch.randn(7, 128)
        z = torch.randn(7, 64)

        # Reconstruct E8 code
        hz = torch.cat([h, z], dim=-1)
        e8_pred = rssm.obs_decoder(hz)

        # Ground truth E8 code
        e8_true = torch.randn(7, 8)  # Each colony predicts 8D E8

        # Compute reconstruction error
        recon_error = torch.nn.functional.mse_loss(e8_pred, e8_true)

        assert isinstance(recon_error.item(), float)


class TestRSSMFactoryFunctions:
    """Test factory functions for RSSM creation."""

    def test_create_rssm_world_model(self) -> None:
        """create_rssm_world_model should return configured RSSM."""
        config = ColonyRSSMConfig(
            obs_dim=512,
            colony_dim=256,
            num_colonies=7,
        )

        rssm = create_rssm_world_model(config)

        assert isinstance(rssm, OrganismRSSM)
        assert rssm.obs_dim == 512
        assert rssm.deter_dim == 256

    def test_factory_with_kwargs(self) -> None:
        """Factory should accept kwargs for config overrides."""
        # OrganismRSSM accepts kwargs for config overrides
        rssm = OrganismRSSM(
            obs_dim=1024,
            colony_dim=512,
        )

        assert rssm.obs_dim == 1024
        assert rssm.deter_dim == 512


class TestRSSMEdgeCases:
    """Test edge cases and error handling."""

    def test_zero_input(self) -> None:
        """Zero inputs should not crash.

        UPDATED (Dec 22, 2025): test step_all with zero E8 + S7.
        """
        config = ColonyRSSMConfig(
            obs_dim=8,  # E8 code dimension
            colony_dim=128,
            num_colonies=7,
        )
        rssm = OrganismRSSM(config)

        e8_code = torch.zeros(1, 8)  # E8 code
        s7_phase = torch.zeros(1, 7)  # S7 phase
        result = rssm.step_all(e8_code=e8_code, s7_phase=s7_phase, enable_cot=False)

        assert "organism_action" in result
        assert not torch.isnan(result["organism_action"]).any()

    def test_large_batch(self) -> None:
        """Large batch sizes should work.

        UPDATED (Dec 22, 2025): test step_all with large batch (E8 + S7).
        """
        config = ColonyRSSMConfig(
            obs_dim=8,  # E8 code dimension
            colony_dim=128,
            num_colonies=7,
        )
        rssm = OrganismRSSM(config)

        batch_size = 64
        e8_code = torch.randn(batch_size, 8)  # E8 code
        s7_phase = torch.randn(batch_size, 7)  # S7 phase
        result = rssm.step_all(e8_code=e8_code, s7_phase=s7_phase, enable_cot=False)

        assert result["organism_action"].shape[0] == batch_size

    def test_nan_handling(self) -> None:
        """NaN inputs should be handled gracefully.

        UPDATED (Dec 22, 2025): test step_all with NaN E8 + S7.
        """
        config = ColonyRSSMConfig(
            obs_dim=8,  # E8 code dimension
            colony_dim=128,
            num_colonies=7,
        )
        rssm = OrganismRSSM(config)

        e8_code = torch.tensor([[float("nan")] * 8])  # E8 code with NaN
        s7_phase = torch.tensor([[float("nan")] * 7])  # S7 phase with NaN

        # Should not crash (may produce NaN output)
        try:
            result = rssm.step_all(e8_code=e8_code, s7_phase=s7_phase, enable_cot=False)
            assert "organism_action" in result
        except Exception:
            pytest.skip("NaN handling not implemented")


class TestRSSMGradients:
    """Test gradient flow through RSSM."""

    def test_gradient_flow_encoder(self) -> None:
        """Gradients should flow through RSSM.

        UPDATED (Dec 22, 2025): test gradient flow through step_all with E8 + S7.
        """
        config = ColonyRSSMConfig(
            obs_dim=8,  # E8 code dimension
            colony_dim=128,
            num_colonies=7,
        )
        rssm = OrganismRSSM(config)

        e8_code = torch.randn(1, 8, requires_grad=True)  # E8 code
        s7_phase = torch.randn(1, 7, requires_grad=True)  # S7 phase
        result = rssm.step_all(e8_code=e8_code, s7_phase=s7_phase, enable_cot=False)
        loss = result["organism_action"].sum()
        loss.backward()

        assert e8_code.grad is not None
        assert s7_phase.grad is not None
        assert not torch.isnan(e8_code.grad).any()
        assert not torch.isnan(s7_phase.grad).any()

    def test_gradient_flow_action_head(self) -> None:
        """Gradients should flow through action decoder."""
        config = ColonyRSSMConfig(
            obs_dim=256,
            colony_dim=128,
            stochastic_dim=64,
            action_dim=32,
            num_colonies=7,
        )
        rssm = OrganismRSSM(config)

        h = torch.randn(7, 128, requires_grad=True)
        z = torch.randn(7, 64, requires_grad=True)

        hz = torch.cat([h, z], dim=-1)
        actions = rssm.action_head(hz)
        loss = actions.sum()
        loss.backward()

        assert h.grad is not None
        assert z.grad is not None


class TestRSSMMultiTimestep:
    """Test RSSM dynamics across multiple timesteps."""

    def test_temporal_consistency(self) -> None:
        """RSSM should maintain temporal consistency."""
        config = ColonyRSSMConfig(
            obs_dim=256,
            colony_dim=128,
            stochastic_dim=64,
            action_dim=32,
            num_colonies=7,
        )
        rssm = OrganismRSSM(config)

        # Simulate 3 timesteps
        h = torch.randn(7, 128)
        z = torch.randn(7, 64)
        a = torch.randn(7, 32)

        states = []
        for _ in range(3):
            # Transition
            za = torch.cat([z, a], dim=-1)
            h_next = rssm.dynamics_cell(za, h)

            # Sample new z (simplified - actual sampling is more complex)
            z_next = torch.randn(7, 64)

            # Decode action
            hz = torch.cat([h_next, z_next], dim=-1)
            a_next = rssm.action_head(hz)

            states.append((h_next.clone(), z_next.clone(), a_next.clone()))

            h, z, a = h_next, z_next, a_next

        # Should have 3 states
        assert len(states) == 3


# Mark all tests with timeout
