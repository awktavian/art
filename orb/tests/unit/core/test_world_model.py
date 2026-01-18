"""Unit Tests: World Model Components

Comprehensive tests for RSSM core, state management, encoding/decoding,
belief state updates, and prediction accuracy.

Created: January 12, 2026
"""

from __future__ import annotations

import pytest
import torch
import torch.nn as nn

# Consolidated markers
pytestmark = [
    pytest.mark.tier_unit,
    pytest.mark.unit,
    pytest.mark.timeout(60),
]


# =============================================================================
# TEST: ColonyState
# =============================================================================


class TestColonyState:
    """Test ColonyState dataclass."""

    def test_colony_state_creation(self) -> None:
        """Test basic ColonyState creation."""
        from kagami.core.world_model.rssm_state import ColonyState

        hidden = torch.randn(4, 64)  # [B, H]
        stochastic = torch.randn(4, 32)  # [B, Z]

        state = ColonyState(
            hidden=hidden,
            stochastic=stochastic,
            colony_id=0,
        )

        assert state.hidden.shape == (4, 64)
        assert state.stochastic.shape == (4, 32)
        assert state.colony_id == 0
        assert state.timestep == 0
        assert state.active is True

    def test_colony_state_invalid_colony_id(self) -> None:
        """Test ColonyState rejects invalid colony_id."""
        from kagami.core.world_model.rssm_state import ColonyState

        hidden = torch.randn(4, 64)
        stochastic = torch.randn(4, 32)

        with pytest.raises(ValueError, match="colony_id must be in"):
            ColonyState(hidden=hidden, stochastic=stochastic, colony_id=7)

        with pytest.raises(ValueError, match="colony_id must be in"):
            ColonyState(hidden=hidden, stochastic=stochastic, colony_id=-1)

    def test_colony_state_batch_size_mismatch(self) -> None:
        """Test ColonyState rejects mismatched batch sizes."""
        from kagami.core.world_model.rssm_state import ColonyState

        hidden = torch.randn(4, 64)
        stochastic = torch.randn(8, 32)  # Different batch size

        with pytest.raises(ValueError, match="same batch size"):
            ColonyState(hidden=hidden, stochastic=stochastic, colony_id=0)

    def test_colony_state_requires_2d_tensors(self) -> None:
        """Test ColonyState requires at least 2D tensors."""
        from kagami.core.world_model.rssm_state import ColonyState

        hidden_1d = torch.randn(64)  # 1D - invalid
        stochastic = torch.randn(4, 32)

        with pytest.raises(ValueError, match="at least 2D"):
            ColonyState(hidden=hidden_1d, stochastic=stochastic, colony_id=0)

    def test_colony_state_clone(self) -> None:
        """Test ColonyState clone creates independent copy."""
        from kagami.core.world_model.rssm_state import ColonyState

        hidden = torch.randn(4, 64)
        stochastic = torch.randn(4, 32)
        state = ColonyState(hidden=hidden, stochastic=stochastic, colony_id=0)

        cloned = state.clone()

        # Verify independence
        assert cloned.hidden is not state.hidden
        assert cloned.stochastic is not state.stochastic
        assert torch.allclose(cloned.hidden, state.hidden)
        assert torch.allclose(cloned.stochastic, state.stochastic)

        # Modify original, verify clone unchanged
        state.hidden.zero_()
        assert not torch.allclose(cloned.hidden, state.hidden)

    def test_colony_state_detach(self) -> None:
        """Test ColonyState detach removes gradient tracking."""
        from kagami.core.world_model.rssm_state import ColonyState

        hidden = torch.randn(4, 64, requires_grad=True)
        stochastic = torch.randn(4, 32, requires_grad=True)
        state = ColonyState(hidden=hidden, stochastic=stochastic, colony_id=0)

        detached = state.detach()

        assert not detached.hidden.requires_grad
        assert not detached.stochastic.requires_grad

    def test_colony_state_to_device(self) -> None:
        """Test ColonyState device transfer."""
        from kagami.core.world_model.rssm_state import ColonyState

        hidden = torch.randn(4, 64)
        stochastic = torch.randn(4, 32)
        state = ColonyState(hidden=hidden, stochastic=stochastic, colony_id=0)

        moved = state.to("cpu")

        assert moved.hidden.device.type == "cpu"
        assert moved.stochastic.device.type == "cpu"

    def test_colony_state_with_attention_weights(self) -> None:
        """Test ColonyState with optional attention weights."""
        from kagami.core.world_model.rssm_state import ColonyState

        hidden = torch.randn(4, 64)
        stochastic = torch.randn(4, 32)
        attention = torch.randn(4, 7, 7)  # [B, 7, 7] colony attention

        state = ColonyState(
            hidden=hidden,
            stochastic=stochastic,
            colony_id=0,
            attention_weights=attention,
        )

        assert state.attention_weights is not None
        assert state.attention_weights.shape == (4, 7, 7)

    def test_colony_state_metadata(self) -> None:
        """Test ColonyState metadata dictionary."""
        from kagami.core.world_model.rssm_state import ColonyState

        hidden = torch.randn(4, 64)
        stochastic = torch.randn(4, 32)

        state = ColonyState(hidden=hidden, stochastic=stochastic, colony_id=0)
        state.metadata["prev_action"] = torch.randn(4, 16)
        state.metadata["custom_key"] = "custom_value"

        assert "prev_action" in state.metadata
        assert state.metadata["custom_key"] == "custom_value"


class TestCreateColonyStates:
    """Test create_colony_states factory function."""

    def test_creates_seven_colonies(self) -> None:
        """Test creates 7 colony states by default."""
        from kagami.core.world_model.rssm_state import create_colony_states

        states = create_colony_states(batch_size=4)

        assert len(states) == 7
        for i, state in enumerate(states):
            assert state.colony_id == i
            assert state.hidden.size(0) == 4

    def test_creates_custom_number_of_colonies(self) -> None:
        """Test creating custom number of colonies."""
        from kagami.core.world_model.rssm_state import create_colony_states

        states = create_colony_states(batch_size=2, num_colonies=3)

        assert len(states) == 3

    def test_creates_on_specified_device(self) -> None:
        """Test creating states on specified device."""
        from kagami.core.world_model.rssm_state import create_colony_states

        states = create_colony_states(batch_size=2, device="cpu")

        for state in states:
            assert state.hidden.device.type == "cpu"

    def test_creates_with_custom_dimensions(self) -> None:
        """Test creating states with custom hidden/stochastic dims."""
        from kagami.core.world_model.rssm_state import create_colony_states

        states = create_colony_states(
            batch_size=2,
            hidden_dim=128,
            stochastic_dim=64,
        )

        for state in states:
            assert state.hidden.shape == (2, 128)
            assert state.stochastic.shape == (2, 64)


# =============================================================================
# TEST: BlockGRU
# =============================================================================


class TestBlockGRU:
    """Test BlockGRU with LayerNorm (DreamerV3 style)."""

    def test_block_gru_forward(self) -> None:
        """Test BlockGRU forward pass."""
        from kagami.core.world_model.rssm_core import BlockGRU

        block_gru = BlockGRU(input_size=32, hidden_size=64, num_blocks=8)

        x = torch.randn(4, 32)  # [B, input_size]
        h = torch.randn(4, 64)  # [B, hidden_size]

        h_new = block_gru(x, h)

        assert h_new.shape == (4, 64)
        assert torch.isfinite(h_new).all()

    def test_block_gru_layer_norm_applied(self) -> None:
        """Test BlockGRU applies layer normalization."""
        from kagami.core.world_model.rssm_core import BlockGRU

        block_gru = BlockGRU(input_size=32, hidden_size=64, num_blocks=8)

        x = torch.randn(4, 32) * 100  # Large values
        h = torch.randn(4, 64)

        h_new = block_gru(x, h)

        # LayerNorm should keep values reasonable
        assert h_new.abs().mean() < 10

    def test_block_gru_gradient_flow(self) -> None:
        """Test gradients flow through BlockGRU."""
        from kagami.core.world_model.rssm_core import BlockGRU

        block_gru = BlockGRU(input_size=32, hidden_size=64, num_blocks=8)

        x = torch.randn(4, 32, requires_grad=True)
        h = torch.randn(4, 64, requires_grad=True)

        h_new = block_gru(x, h)
        loss = h_new.sum()
        loss.backward()

        assert x.grad is not None
        assert h.grad is not None
        assert torch.isfinite(x.grad).all()


# =============================================================================
# TEST: DiscreteLatentEncoder
# =============================================================================


class TestDiscreteLatentEncoder:
    """Test DiscreteLatentEncoder (DreamerV3 32x32 categorical)."""

    def test_discrete_encoder_output_shape(self) -> None:
        """Test DiscreteLatentEncoder output shapes."""
        from kagami.core.world_model.rssm_core import DiscreteLatentEncoder

        encoder = DiscreteLatentEncoder(input_dim=64, num_categories=32, num_classes=32)

        x = torch.randn(4, 64)
        samples, logits = encoder(x)

        assert samples.shape == (4, 32 * 32)  # [B, num_categories * num_classes]
        assert logits.shape == (4, 32, 32)  # [B, num_categories, num_classes]

    def test_discrete_encoder_samples_one_hot(self) -> None:
        """Test DiscreteLatentEncoder samples are one-hot in eval mode."""
        from kagami.core.world_model.rssm_core import DiscreteLatentEncoder

        encoder = DiscreteLatentEncoder(input_dim=64, num_categories=32, num_classes=32)
        encoder.eval()

        x = torch.randn(4, 64)
        samples, _ = encoder(x)

        # Reshape to check one-hot
        samples_reshaped = samples.view(4, 32, 32)  # [B, 32, 32]

        # Each category should sum to 1 (one-hot)
        category_sums = samples_reshaped.sum(dim=-1)
        assert torch.allclose(category_sums, torch.ones_like(category_sums))

    def test_discrete_encoder_gradient_flow(self) -> None:
        """Test gradients flow through DiscreteLatentEncoder."""
        from kagami.core.world_model.rssm_core import DiscreteLatentEncoder

        encoder = DiscreteLatentEncoder(input_dim=64, num_categories=32, num_classes=32)
        encoder.train()

        x = torch.randn(4, 64, requires_grad=True)
        samples, logits = encoder(x)

        loss = samples.sum() + logits.sum()
        loss.backward()

        assert x.grad is not None
        assert torch.isfinite(x.grad).all()


# =============================================================================
# TEST: OrganismRSSM
# =============================================================================


class TestOrganismRSSM:
    """Test OrganismRSSM (7-colony RSSM system)."""

    @pytest.fixture
    def rssm(self):
        """Create OrganismRSSM for testing."""
        from kagami.core.world_model.colony_rssm import ColonyRSSMConfig, OrganismRSSM

        config = ColonyRSSMConfig()
        return OrganismRSSM(config=config)

    def test_rssm_initialization(self, rssm) -> None:
        """Test OrganismRSSM initializes correctly."""
        assert rssm.num_colonies == 7
        assert rssm.deter_dim > 0
        assert rssm.stoch_dim > 0
        assert rssm.action_dim > 0

    def test_rssm_initialize_all(self, rssm) -> None:
        """Test OrganismRSSM.initialize_all creates states."""
        assert rssm.get_current_states() is None

        rssm.initialize_all(batch_size=4)

        states = rssm.get_current_states()
        assert states is not None
        assert len(states) == 7

    def test_rssm_step_all_with_e8_s7(self, rssm) -> None:
        """Test OrganismRSSM.step_all with E8 code and S7 phase."""
        e8_code = torch.randn(2, 8)  # [B, 8]
        s7_phase = torch.randn(2, 7)  # [B, 7]

        result = rssm.step_all(e8_code=e8_code, s7_phase=s7_phase)

        assert "organism_action" in result
        assert "h_next" in result
        assert "z_next" in result
        assert "kl" in result
        assert result["h_next"].shape[1] == 7  # 7 colonies

    def test_rssm_step_function(self, rssm) -> None:
        """Test OrganismRSSM.step for planning (non-mutating)."""
        B = 2
        h_prev = torch.randn(B, 7, rssm.deter_dim)
        z_prev = torch.randn(B, 7, rssm.stoch_dim)
        action = torch.randn(B, 7, rssm.action_dim)
        e8_code = torch.randn(B, 8)
        s7_phase = torch.randn(B, 7)

        h_next, z_next, info = rssm.step(
            h_prev=h_prev,
            z_prev=z_prev,
            action=action,
            e8_code=e8_code,
            s7_phase=s7_phase,
        )

        assert h_next.shape == (B, 7, rssm.deter_dim)
        assert z_next.shape == (B, 7, rssm.stoch_dim)
        assert "kl" in info

    def test_rssm_forward_sequence(self, rssm) -> None:
        """Test OrganismRSSM.forward with sequence input."""
        B, T = 2, 4
        e8_code = torch.randn(B, T, 8)
        s7_phase = torch.randn(B, T, 7)

        result = rssm.forward(e8_code, s7_phase)

        assert result["h"].shape == (B, T, 7, rssm.deter_dim)
        assert result["z"].shape == (B, T, 7, rssm.stoch_dim)
        assert result["kl"].shape == (B, T, 7)

    def test_rssm_predict_obs(self, rssm) -> None:
        """Test OrganismRSSM.predict_obs (E8 prediction)."""
        B = 2
        h = torch.randn(B, 7, rssm.deter_dim)
        z = torch.randn(B, 7, rssm.stoch_dim)

        e8_pred = rssm.predict_obs(h, z)

        assert e8_pred.shape == (B, 8)

    def test_rssm_predict_reward(self, rssm) -> None:
        """Test OrganismRSSM.predict_reward."""
        B = 2
        h = torch.randn(B, rssm.deter_dim)
        z = torch.randn(B, rssm.stoch_dim)

        reward = rssm.predict_reward(h, z)

        assert reward.shape == (B,)
        assert torch.isfinite(reward).all()

    def test_rssm_predict_value(self, rssm) -> None:
        """Test OrganismRSSM.predict_value."""
        B = 2
        h = torch.randn(B, rssm.deter_dim)
        z = torch.randn(B, rssm.stoch_dim)

        value = rssm.predict_value(h, z)

        assert value.shape == (B,)
        assert torch.isfinite(value).all()

    def test_rssm_predict_continue(self, rssm) -> None:
        """Test OrganismRSSM.predict_continue."""
        B = 2
        h = torch.randn(B, rssm.deter_dim)
        z = torch.randn(B, rssm.stoch_dim)

        cont = rssm.predict_continue(h, z)

        assert cont.shape == (B, 1)
        assert (cont >= 0).all()
        assert (cont <= 1).all()  # Probability

    def test_rssm_imagine_trajectory(self, rssm) -> None:
        """Test OrganismRSSM.imagine for trajectory planning."""
        B, depth = 2, 5
        h_init = torch.randn(B, rssm.deter_dim)
        z_init = torch.randn(B, rssm.stoch_dim)
        policy = torch.randn(B, depth, rssm.action_dim)

        result = rssm.imagine(h_init, z_init, policy)

        assert result["h_states"].shape == (B, depth, rssm.deter_dim)
        assert result["z_states"].shape == (B, depth, rssm.stoch_dim)
        assert result["e8_predictions"].shape == (B, depth, 8)

    def test_rssm_episode_boundaries(self, rssm) -> None:
        """Test OrganismRSSM handles episode boundaries."""
        B, T = 2, 4
        e8_code = torch.randn(B, T, 8)
        s7_phase = torch.randn(B, T, 7)

        # Episode ends at t=2
        continue_flags = torch.ones(B, T)
        continue_flags[:, 2] = 0

        result = rssm.forward(e8_code, s7_phase, continue_flags=continue_flags)

        assert torch.isfinite(result["h"]).all()
        assert torch.isfinite(result["z"]).all()

    def test_rssm_gradient_flow(self, rssm) -> None:
        """Test gradients flow through OrganismRSSM."""
        B, T = 2, 4
        e8_code = torch.randn(B, T, 8, requires_grad=True)
        s7_phase = torch.randn(B, T, 7, requires_grad=True)

        result = rssm.forward(e8_code, s7_phase, sample=False)

        loss = result["h"].sum() + result["z"].sum()
        loss.backward()

        assert e8_code.grad is not None
        assert s7_phase.grad is not None
        assert torch.isfinite(e8_code.grad).all()

    def test_rssm_unimix_probability_floor(self, rssm) -> None:
        """Test unimix enforces probability floor."""
        e8_code = torch.randn(2, 8)
        s7_phase = torch.randn(2, 7)

        result = rssm.step_all(e8_code=e8_code, s7_phase=s7_phase)

        probs = result["posterior_probs"]
        K = rssm.latent_classes

        # After unimix, min prob >= unimix/K
        floor = rssm.unimix * (1.0 / float(K))
        assert float(probs.min().item()) >= floor - 1e-7

    def test_rssm_reset_states(self, rssm) -> None:
        """Test OrganismRSSM.reset_states."""
        rssm.initialize_all(batch_size=4)
        rssm.step_all(e8_code=torch.randn(4, 8), s7_phase=torch.randn(4, 7))

        # Reset
        rssm.reset_states(batch_size=2, device="cpu")

        states = rssm.get_current_states()
        assert states is not None
        assert len(states) == 7
        assert states[0].hidden.size(0) == 2


# =============================================================================
# TEST: Numerical Stability
# =============================================================================


class TestRSSMNumericalStability:
    """Test RSSM numerical stability under extreme conditions."""

    @pytest.fixture
    def rssm(self):
        from kagami.core.world_model.colony_rssm import ColonyRSSMConfig, OrganismRSSM

        return OrganismRSSM(config=ColonyRSSMConfig())

    def test_large_input_values(self, rssm) -> None:
        """Test stability with large input values."""
        e8_code = torch.randn(2, 8) * 100
        s7_phase = torch.randn(2, 7) * 100

        result = rssm.step_all(e8_code=e8_code, s7_phase=s7_phase)

        assert torch.isfinite(result["organism_action"]).all()
        assert torch.isfinite(result["h_next"]).all()

    def test_small_input_values(self, rssm) -> None:
        """Test stability with very small input values."""
        e8_code = torch.randn(2, 8) * 1e-8
        s7_phase = torch.randn(2, 7) * 1e-8

        result = rssm.step_all(e8_code=e8_code, s7_phase=s7_phase)

        assert torch.isfinite(result["organism_action"]).all()

    def test_zero_inputs(self, rssm) -> None:
        """Test stability with zero inputs."""
        e8_code = torch.zeros(2, 8)
        s7_phase = torch.zeros(2, 7)

        result = rssm.step_all(e8_code=e8_code, s7_phase=s7_phase)

        assert torch.isfinite(result["organism_action"]).all()

    def test_long_sequence_stability(self, rssm) -> None:
        """Test stability over long sequences."""
        B, T = 2, 100
        e8_code = torch.randn(B, T, 8)
        s7_phase = torch.randn(B, T, 7)

        result = rssm.forward(e8_code, s7_phase)

        # No NaN/Inf even after 100 steps
        assert torch.isfinite(result["h"]).all()
        assert torch.isfinite(result["z"]).all()


# =============================================================================
# TEST: TwoHot Encoding
# =============================================================================


class TestTwoHotEncoder:
    """Test TwoHot encoding for reward/value prediction."""

    def test_twohot_encode_produces_distribution(self) -> None:
        """Test TwoHot encode produces valid probability distribution."""
        from kagami.core.world_model.dreamer_transforms import TwoHotEncoder

        encoder = TwoHotEncoder(num_bins=255, low=-20.0, high=20.0)

        # Test values
        values = torch.tensor([0.0, 5.0, -5.0, 10.0, -10.0])

        # Encode to twohot distribution
        encoded = encoder.encode(values)  # [5, 255] twohot targets

        # Should be valid distribution (sums to 1, non-negative)
        assert encoded.shape == (5, 255)
        assert (encoded >= 0).all()
        assert torch.allclose(encoded.sum(dim=-1), torch.ones(5), atol=1e-5)

        # Should be twohot (at most 2 non-zero values per row)
        nonzero_counts = (encoded > 1e-7).sum(dim=-1)
        assert (nonzero_counts <= 2).all()

    def test_twohot_decode_from_logits(self) -> None:
        """Test TwoHot decode from logits."""
        from kagami.core.world_model.dreamer_transforms import TwoHotEncoder

        encoder = TwoHotEncoder(num_bins=255, low=-20.0, high=20.0)

        # Create logits that peak at specific bins
        logits = torch.randn(4, 255)
        decoded = encoder.decode(logits)

        # Should produce scalar per sample
        assert decoded.shape == (4,)
        assert torch.isfinite(decoded).all()

    def test_twohot_loss_computation(self) -> None:
        """Test TwoHot loss computation."""
        from kagami.core.world_model.dreamer_transforms import TwoHotEncoder

        encoder = TwoHotEncoder(num_bins=255, low=-20.0, high=20.0)

        logits = torch.randn(4, 255)
        targets = torch.tensor([1.0, 2.0, -1.0, 0.0])

        loss = encoder.loss(logits, targets)

        assert loss.shape == ()  # Scalar
        assert torch.isfinite(loss)
        assert loss > 0

    def test_twohot_matching_logits_and_targets_lower_loss(self) -> None:
        """Test that matching logits and targets produce lower loss."""
        from kagami.core.world_model.dreamer_transforms import TwoHotEncoder

        encoder = TwoHotEncoder(num_bins=255, low=-20.0, high=20.0)

        targets = torch.tensor([0.0, 5.0, -5.0])

        # Create logits from targets (should produce low loss)
        good_logits = encoder.encode(targets) * 10  # Scale up for sharper dist

        # Random logits (should produce higher loss)
        bad_logits = torch.randn(3, 255)

        good_loss = encoder.loss(good_logits, targets)
        bad_loss = encoder.loss(bad_logits, targets)

        # Good logits should have lower loss
        assert good_loss < bad_loss


# =============================================================================
# TEST: Balanced KL Loss
# =============================================================================


class TestBalancedKLLoss:
    """Test DreamerV3 balanced KL loss."""

    def test_balanced_kl_categorical(self) -> None:
        """Test balanced_kl_loss_categorical."""
        from kagami.core.world_model.dreamer_transforms import balanced_kl_loss_categorical

        # Create probability distributions
        post_probs = torch.softmax(torch.randn(4, 7, 240), dim=-1)
        prior_probs = torch.softmax(torch.randn(4, 7, 240), dim=-1)

        loss, info = balanced_kl_loss_categorical(
            post_probs=post_probs,
            prior_probs=prior_probs,
            free_bits=1.0,
            dyn_weight=0.8,
            rep_weight=0.2,
        )

        assert torch.isfinite(loss)
        assert "kl_dyn" in info
        assert "kl_rep" in info
        assert "kl_raw" in info

    def test_balanced_kl_free_bits(self) -> None:
        """Test free_bits clipping in balanced KL."""
        from kagami.core.world_model.dreamer_transforms import balanced_kl_loss_categorical

        # Identical distributions = KL near 0
        probs = torch.softmax(torch.randn(4, 7, 240), dim=-1)

        loss, info = balanced_kl_loss_categorical(
            post_probs=probs,
            prior_probs=probs,
            free_bits=1.0,  # Floor at 1.0 nats
        )

        # Raw KL should be near 0, but loss should be >= 0 (clipped)
        assert info["kl_raw"] < 0.1  # Near 0
        assert loss >= 0


# =============================================================================
# TEST: Factory Functions
# =============================================================================


class TestRSSMFactory:
    """Test RSSM factory and singleton functions."""

    def test_create_rssm_world_model(self) -> None:
        """Test create_rssm_world_model factory."""
        from kagami.core.world_model.rssm_core import create_rssm_world_model

        model = create_rssm_world_model()

        assert model is not None
        assert model.num_colonies == 7

    def test_get_organism_rssm_singleton(self) -> None:
        """Test get_organism_rssm returns singleton."""
        from kagami.core.world_model.rssm_core import (
            get_organism_rssm,
            reset_organism_rssm,
        )

        # Reset first
        reset_organism_rssm()

        rssm1 = get_organism_rssm()
        rssm2 = get_organism_rssm()

        # Same instance
        assert rssm1 is rssm2

        # Cleanup
        reset_organism_rssm()

    def test_reset_organism_rssm(self) -> None:
        """Test reset_organism_rssm clears singleton."""
        from kagami.core.world_model.rssm_core import (
            get_organism_rssm,
            reset_organism_rssm,
        )

        rssm1 = get_organism_rssm()
        reset_organism_rssm()
        rssm2 = get_organism_rssm()

        # Different instances after reset
        assert rssm1 is not rssm2

        # Cleanup
        reset_organism_rssm()


# =============================================================================
# TEST: Encoder/Decoder Structure
# =============================================================================


class TestEncoderDecoder:
    """Test Encoder and Decoder components."""

    def test_encoder_validates_input_shape(self) -> None:
        """Test Encoder validates input tensor shape."""
        from unittest.mock import MagicMock, PropertyMock

        from kagami.core.world_model.encoder import Encoder

        # Create mock hourglass
        mock_hourglass = MagicMock()
        mock_config = MagicMock()
        mock_config.bulk_dim = 512
        mock_config.tower_dim = 64
        mock_config.training_levels = 8
        mock_config.inference_levels = 8
        type(mock_hourglass).config = PropertyMock(return_value=mock_config)

        encoder = Encoder(mock_hourglass)

        # 1D tensor should fail
        with pytest.raises(ValueError, match="must be 2D.*or 3D"):
            encoder(torch.randn(512))

        # 4D tensor should fail
        with pytest.raises(ValueError, match="must be 2D.*or 3D"):
            encoder(torch.randn(2, 4, 8, 512))

    def test_decoder_validates_e8_dimension(self) -> None:
        """Test Decoder validates E8 VQ dimension."""
        from unittest.mock import MagicMock, PropertyMock

        from kagami.core.world_model.decoder import Decoder

        # Create mock hourglass
        mock_hourglass = MagicMock()
        mock_config = MagicMock()
        mock_config.bulk_dim = 512
        mock_config.tower_dim = 64
        type(mock_hourglass).config = PropertyMock(return_value=mock_config)

        decoder = Decoder(mock_hourglass)

        # Wrong dimension should fail
        with pytest.raises(ValueError, match="8D E8 VQ"):
            decoder(torch.randn(4, 16))  # 16 instead of 8


# =============================================================================
# TEST: S7 Hierarchy Fusion
# =============================================================================


class TestS7HierarchyFusion:
    """Test S7 hierarchy fusion (E8->E7->E6->F4->G2)."""

    @pytest.fixture
    def rssm(self):
        from kagami.core.world_model.colony_rssm import ColonyRSSMConfig, OrganismRSSM

        return OrganismRSSM(config=ColonyRSSMConfig())

    def test_s7_fusion_primary_only(self, rssm) -> None:
        """Test S7 fusion with only primary phase."""
        s7_phase = torch.randn(4, 7)

        fused, info = rssm._fuse_s7_hierarchy(s7_phase)

        assert fused.shape == (4, 7)
        assert info["fusion_mode"] == "primary_only"
        assert info["coherence"] == 1.0

    def test_s7_fusion_with_hierarchy(self, rssm) -> None:
        """Test S7 fusion with full hierarchy."""
        s7_phase = torch.randn(4, 7)
        s7_e8 = torch.randn(4, 7)
        s7_e7 = torch.randn(4, 7)
        s7_e6 = torch.randn(4, 7)
        s7_f4 = torch.randn(4, 7)

        fused, info = rssm._fuse_s7_hierarchy(
            s7_phase,
            s7_e8=s7_e8,
            s7_e7=s7_e7,
            s7_e6=s7_e6,
            s7_f4=s7_f4,
        )

        assert fused.shape == (4, 7)
        assert "coherence" in info
