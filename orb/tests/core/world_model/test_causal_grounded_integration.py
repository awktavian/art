"""Tests for Causal Grounded Intelligence Integration.

Tests the three-layer cognitive enhancement from "Kagami Evolution":
1. Causal Reasoning Engine - counterfactual reasoning
2. Temporal Abstraction Layer - long-horizon planning
3. Embodied Sensorimotor Input - physics grounding
"""

import pytest
import torch

from kagami.core.world_model.causal_grounded_integration import (
    CausalGroundedWorldModel,
    CausalReasoningEngine,
    CounterfactualQuery,
    CounterfactualResult,
    GroundedIntelligenceConfig,
    HierarchicalPlanResult,
    MacroAction,
    SensorimotorEncoder,
    TemporalAbstractionLayer,
    get_causal_grounded_world_model,
    reset_causal_grounded_world_model,
)


class TestCausalReasoningEngine:
    """Tests for Layer 1: Causal Reasoning Engine."""

    def test_init(self) -> None:
        """Test engine initialization."""
        engine = CausalReasoningEngine(obs_dim=8, action_dim=8)
        assert engine.obs_dim == 8
        assert engine.action_dim == 8

    def test_forward(self) -> None:
        """Test forward prediction."""
        engine = CausalReasoningEngine(obs_dim=8, action_dim=8)

        obs = torch.randn(4, 8)
        action = torch.randn(4, 8)

        next_state = engine(obs, action)

        assert next_state.shape == (4, 8)

    def test_abduction(self) -> None:
        """Test exogenous variable inference."""
        engine = CausalReasoningEngine(obs_dim=8, action_dim=8)

        obs = torch.randn(4, 8)
        action = torch.randn(4, 8)
        next_obs = torch.randn(4, 8)

        U = engine.abduction(obs, action, next_obs)

        assert U.shape == (4, 8)

    def test_counterfactual(self) -> None:
        """Test full counterfactual computation."""
        engine = CausalReasoningEngine(obs_dim=8, action_dim=8)

        query = CounterfactualQuery(
            observation=torch.randn(4, 8),
            factual_action=torch.randn(4, 8),
            counterfactual_action=torch.randn(4, 8),
        )

        result = engine.counterfactual(query)

        assert isinstance(result, CounterfactualResult)
        assert result.factual_outcome.shape == (4, 8)
        assert result.counterfactual_outcome.shape == (4, 8)
        assert result.causal_effect.shape == (4, 8)
        assert 0.0 <= result.confidence <= 1.0

    def test_counterfactual_with_abduction(self) -> None:
        """Test counterfactual with actual next observation for abduction."""
        engine = CausalReasoningEngine(obs_dim=8, action_dim=8)

        query = CounterfactualQuery(
            observation=torch.randn(4, 8),
            factual_action=torch.randn(4, 8),
            counterfactual_action=torch.randn(4, 8),
        )
        next_obs = torch.randn(4, 8)

        result = engine.counterfactual(query, next_observation=next_obs)

        assert isinstance(result, CounterfactualResult)
        # With abduction, exogenous variables should be non-zero
        # (unless by chance the network outputs zeros)


class TestTemporalAbstractionLayer:
    """Tests for Layer 2: Temporal Abstraction Layer."""

    def test_init(self) -> None:
        """Test layer initialization."""
        layer = TemporalAbstractionLayer(
            state_dim=64,
            subgoal_dim=32,
            action_dim=8,
            n_subgoals=8,
        )
        assert layer.state_dim == 64
        assert layer.subgoal_dim == 32
        assert layer.n_subgoals == 8

    def test_encode_to_subgoal(self) -> None:
        """Test subgoal encoding."""
        layer = TemporalAbstractionLayer(state_dim=64, subgoal_dim=32)

        state = torch.randn(4, 64)
        subgoal = layer.encode_to_subgoal(state)

        assert subgoal.shape == (4, 32)

    def test_discover_subgoal(self) -> None:
        """Test subgoal discovery."""
        layer = TemporalAbstractionLayer(state_dim=64, subgoal_dim=32, n_subgoals=8)

        state = torch.randn(1, 64)
        subgoal_id, subgoal_state = layer.discover_subgoal(state)

        assert 0 <= subgoal_id < 8
        assert subgoal_state.shape == (1, 32)

    def test_select_subgoal(self) -> None:
        """Test high-level subgoal selection."""
        layer = TemporalAbstractionLayer(state_dim=64, subgoal_dim=32, n_subgoals=8)

        state = torch.randn(4, 64)
        logits, selected = layer.select_subgoal(state)

        assert logits.shape == (4, 8)
        assert selected.shape == (4, 32)

    def test_get_primitive_action(self) -> None:
        """Test low-level action generation."""
        layer = TemporalAbstractionLayer(state_dim=64, subgoal_dim=32, action_dim=8)

        state = torch.randn(4, 64)
        subgoal = torch.randn(4, 32)

        action = layer.get_primitive_action(state, subgoal)

        assert action.shape == (4, 8)

    def test_should_terminate(self) -> None:
        """Test termination prediction."""
        layer = TemporalAbstractionLayer(state_dim=64, subgoal_dim=32)

        state = torch.randn(4, 64)
        subgoal = torch.randn(4, 32)

        term_prob = layer.should_terminate(state, subgoal)

        assert term_prob.shape == (4, 1)
        assert (term_prob >= 0.0).all()
        assert (term_prob <= 1.0).all()


class TestSensorimotorEncoder:
    """Tests for Layer 3: Embodied Sensorimotor Input."""

    def test_init(self) -> None:
        """Test encoder initialization."""
        encoder = SensorimotorEncoder(physics_dim=32, e8_dim=8)
        assert encoder.physics_dim == 32
        assert encoder.e8_dim == 8

    def test_encode(self) -> None:
        """Test physics to E8 encoding."""
        encoder = SensorimotorEncoder(physics_dim=32, e8_dim=8)

        physics_state = torch.randn(4, 32)
        e8_code = encoder.encode(physics_state)

        assert e8_code.shape == (4, 8)

    def test_encode_sequence(self) -> None:
        """Test encoding a sequence of physics states."""
        encoder = SensorimotorEncoder(physics_dim=32, e8_dim=8)

        physics_state = torch.randn(4, 16, 32)  # [B, T, D]
        e8_code = encoder.encode(physics_state)

        assert e8_code.shape == (4, 16, 8)

    def test_decode(self) -> None:
        """Test E8 to physics decoding."""
        encoder = SensorimotorEncoder(physics_dim=32, e8_dim=8)

        e8_code = torch.randn(4, 8)
        physics_reconstructed = encoder.decode(e8_code)

        assert physics_reconstructed.shape == (4, 32)

    def test_forward_roundtrip(self) -> None:
        """Test encode-decode roundtrip."""
        encoder = SensorimotorEncoder(physics_dim=32, e8_dim=8)

        physics_state = torch.randn(4, 32)
        e8_code, reconstructed = encoder(physics_state)

        assert e8_code.shape == (4, 8)
        assert reconstructed.shape == (4, 32)


class TestCausalGroundedWorldModel:
    """Tests for the unified CausalGroundedWorldModel."""

    def test_init_all_enabled(self) -> None:
        """Test initialization with all layers enabled."""
        config = GroundedIntelligenceConfig(
            enable_causal=True,
            enable_temporal=True,
            enable_embodied=True,
        )
        model = CausalGroundedWorldModel(config)

        assert model.causal_engine is not None
        assert model.temporal_abstraction is not None
        assert model.sensorimotor_encoder is not None

    def test_init_selective(self) -> None:
        """Test initialization with selective layers."""
        config = GroundedIntelligenceConfig(
            enable_causal=True,
            enable_temporal=False,
            enable_embodied=False,
        )
        model = CausalGroundedWorldModel(config)

        assert model.causal_engine is not None
        assert model.temporal_abstraction is None
        assert model.sensorimotor_encoder is None

    def test_counterfactual_method(self) -> None:
        """Test counterfactual method on unified model."""
        model = CausalGroundedWorldModel()

        query = CounterfactualQuery(
            observation=torch.randn(4, 8),
            factual_action=torch.randn(4, 8),
            counterfactual_action=torch.randn(4, 8),
        )

        result = model.counterfactual(query)

        assert isinstance(result, CounterfactualResult)

    def test_encode_sensorimotor_method(self) -> None:
        """Test sensorimotor encoding method."""
        model = CausalGroundedWorldModel()

        physics_state = torch.randn(4, 32)
        e8_code = model.encode_sensorimotor(physics_state)

        assert e8_code.shape == (4, 8)

    def test_grounded_forward(self) -> None:
        """Test grounded forward pass."""
        model = CausalGroundedWorldModel()

        physics_state = torch.randn(4, 32)
        result = model.grounded_forward(physics_state)

        assert "e8_code" in result
        assert "physics_reconstructed" in result
        assert "reconstruction_loss" in result
        assert result["e8_code"].shape == (4, 8)


class TestSingleton:
    """Tests for singleton factory functions."""

    def test_get_causal_grounded_world_model(self) -> None:
        """Test singleton factory."""
        reset_causal_grounded_world_model()

        model1 = get_causal_grounded_world_model()
        model2 = get_causal_grounded_world_model()

        assert model1 is model2

    def test_reset_singleton(self) -> None:
        """Test singleton reset."""
        model1 = get_causal_grounded_world_model()
        reset_causal_grounded_world_model()
        model2 = get_causal_grounded_world_model()

        assert model1 is not model2


class TestDataclasses:
    """Tests for data classes."""

    def test_counterfactual_query(self) -> None:
        """Test CounterfactualQuery dataclass."""
        query = CounterfactualQuery(
            observation=torch.randn(4, 8),
            factual_action=torch.randn(4, 8),
            counterfactual_action=torch.randn(4, 8),
            query_variable="next_state",
        )

        assert query.query_variable == "next_state"
        assert query.observation.shape == (4, 8)

    def test_counterfactual_result(self) -> None:
        """Test CounterfactualResult dataclass."""
        result = CounterfactualResult(
            factual_outcome=torch.randn(4, 8),
            counterfactual_outcome=torch.randn(4, 8),
            causal_effect=torch.randn(4, 8),
            confidence=0.85,
        )

        assert result.confidence == 0.85

    def test_macro_action(self) -> None:
        """Test MacroAction dataclass."""
        action = MacroAction(
            name="reach_subgoal_0",
            subgoal=torch.randn(32),
            policy_id=0,
            expected_duration=10,
        )

        assert action.name == "reach_subgoal_0"
        assert action.expected_duration == 10

    def test_grounded_intelligence_config(self) -> None:
        """Test GroundedIntelligenceConfig dataclass."""
        config = GroundedIntelligenceConfig(
            obs_dim=8,
            action_dim=8,
            enable_causal=True,
            enable_temporal=True,
            enable_embodied=True,
        )

        assert config.obs_dim == 8
        assert config.enable_causal is True
