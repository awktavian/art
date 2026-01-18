"""Tests for AgentModel and related dataclasses.

Validates:
1. AgentModel initialization and forward pass
2. AgentBelief, AgentIntent, AgentKnowledge dataclasses
3. AgentState management and E8 embedding
4. Prediction accuracy (action, goal, surprise)

Created: December 21, 2025
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.tier_unit

import time

import torch

from kagami.core.symbiote.agent_model import (
    AgentBelief,
    AgentIntent,
    AgentKnowledge,
    AgentModel,
    AgentState,
    AgentType,
    ConfidenceLevel,
    create_agent_model,
)

# =============================================================================
# FIXTURES
# =============================================================================


@pytest.fixture
def agent_model() -> AgentModel:
    """Create a basic AgentModel for testing."""
    return create_agent_model(
        agent_id="test_user_001",
        agent_type=AgentType.USER,
        state_dim=64,
        e8_dim=8,
        hidden_dim=128,
        num_actions=32,
        num_goals=16,
    )


@pytest.fixture
def sample_features() -> torch.Tensor:
    """Create sample feature tensor."""
    return torch.randn(1, 64)


@pytest.fixture
def batch_features() -> torch.Tensor:
    """Create batch feature tensor."""
    return torch.randn(4, 64)


# =============================================================================
# AGENT MODEL TESTS
# =============================================================================


class TestAgentModelInitialization:
    """Test AgentModel initialization."""

    def test_basic_initialization(self, agent_model: AgentModel) -> None:
        """Test basic model initialization."""
        assert agent_model.agent_id == "test_user_001"
        assert agent_model.agent_type == AgentType.USER
        assert agent_model.state_dim == 64
        assert agent_model.e8_dim == 8

    def test_different_agent_types(self) -> None:
        """Test initialization with different agent types."""
        for agent_type in AgentType:
            model = create_agent_model(
                agent_id=f"test_{agent_type.value}",
                agent_type=agent_type,
            )
            assert model.agent_type == agent_type

    def test_custom_dimensions(self) -> None:
        """Test initialization with custom dimensions."""
        model = create_agent_model(
            agent_id="custom",
            state_dim=128,
            e8_dim=8,
            hidden_dim=256,
            num_actions=64,
            num_goals=32,
        )
        assert model.state_dim == 128
        assert model.e8_dim == 8


class TestAgentModelForward:
    """Test AgentModel forward pass."""

    def test_encode_state(self, agent_model: AgentModel, sample_features: torch.Tensor) -> None:
        """Test state encoding to E8 latent."""
        e8_latent = agent_model.encode_state(sample_features)
        assert e8_latent.shape == (1, 8)
        # Check E8 embedding is not all zeros
        assert e8_latent.abs().sum() > 0

    def test_forward_without_observation(
        self, agent_model: AgentModel, sample_features: torch.Tensor
    ) -> None:
        """Test forward pass without observation."""
        result = agent_model(sample_features)

        assert "e8_latent" in result
        assert "action_logits" in result
        assert "action_probs" in result
        assert "goal_logits" in result
        assert "goal_probs" in result
        assert "intent_confidence" in result

        # Check shapes
        assert result["e8_latent"].shape == (1, 8)
        assert result["action_probs"].shape == (1, 32)
        assert result["goal_probs"].shape == (1, 16)

        # Check probabilities sum to 1
        assert torch.allclose(result["action_probs"].sum(dim=-1), torch.ones(1), atol=1e-5)
        assert torch.allclose(result["goal_probs"].sum(dim=-1), torch.ones(1), atol=1e-5)

    def test_forward_with_observation(
        self, agent_model: AgentModel, sample_features: torch.Tensor
    ) -> None:
        """Test forward pass with observation (for surprise estimation)."""
        observation = torch.randn(1, 64)
        result = agent_model(sample_features, observation=observation)

        assert "e8_next" in result
        assert "surprise" in result
        assert result["surprise"].shape == (1,)
        # Surprise should be non-negative (Softplus output)
        assert (result["surprise"] >= 0).all()

    def test_batch_forward(self, agent_model: AgentModel, batch_features: torch.Tensor) -> None:
        """Test forward pass with batched input."""
        result = agent_model(batch_features)

        assert result["e8_latent"].shape == (4, 8)
        assert result["action_probs"].shape == (4, 32)
        assert result["intent_confidence"].shape == (4,)


class TestAgentModelPredictions:
    """Test individual prediction methods."""

    def test_predict_action(self, agent_model: AgentModel, sample_features: torch.Tensor) -> None:
        """Test action prediction."""
        e8_latent = agent_model.encode_state(sample_features)
        logits, probs = agent_model.predict_action(e8_latent)

        assert logits.shape == (1, 32)
        assert probs.shape == (1, 32)
        assert torch.allclose(probs.sum(dim=-1), torch.ones(1), atol=1e-5)

    def test_predict_goals(self, agent_model: AgentModel, sample_features: torch.Tensor) -> None:
        """Test goal inference."""
        e8_latent = agent_model.encode_state(sample_features)
        logits, probs = agent_model.predict_goals(e8_latent)

        assert logits.shape == (1, 16)
        assert probs.shape == (1, 16)
        assert torch.allclose(probs.sum(dim=-1), torch.ones(1), atol=1e-5)

    def test_estimate_surprise(
        self, agent_model: AgentModel, sample_features: torch.Tensor
    ) -> None:
        """Test surprise estimation."""
        e8_latent = agent_model.encode_state(sample_features)
        observation = torch.randn(1, 64)
        surprise = agent_model.estimate_surprise(e8_latent, observation)

        assert surprise.shape == (1,)
        assert (surprise >= 0).all()  # Non-negative

    def test_intent_confidence(
        self, agent_model: AgentModel, sample_features: torch.Tensor
    ) -> None:
        """Test intent confidence scoring."""
        e8_latent = agent_model.encode_state(sample_features)
        confidence = agent_model.get_intent_confidence(e8_latent)

        assert confidence.shape == (1,)
        assert (confidence >= 0).all() and (confidence <= 1).all()


# =============================================================================
# DATACLASS TESTS
# =============================================================================


class TestAgentBelief:
    """Test AgentBelief dataclass."""

    def test_basic_creation(self) -> None:
        """Test basic belief creation."""
        belief = AgentBelief(
            proposition="User wants to build a web app",
            confidence=0.8,
            source="inferred",
        )
        assert belief.proposition == "User wants to build a web app"
        assert belief.confidence == 0.8
        assert belief.source == "inferred"
        assert belief.belief_id  # Should have auto-generated ID

    def test_false_belief_detection(self) -> None:
        """Test false belief property."""
        true_belief = AgentBelief(proposition="X is true", is_true=True)
        false_belief = AgentBelief(proposition="Y is true", is_true=False)
        unknown_belief = AgentBelief(proposition="Z is true", is_true=None)

        assert not true_belief.is_false_belief
        assert false_belief.is_false_belief
        assert not unknown_belief.is_false_belief


class TestAgentIntent:
    """Test AgentIntent dataclass."""

    def test_basic_creation(self) -> None:
        """Test basic intent creation."""
        intent = AgentIntent(
            action="create_file",
            target="main.py",
            purpose="implement feature",
            confidence=0.7,
        )
        assert intent.action == "create_file"
        assert intent.target == "main.py"
        assert intent.confidence == 0.7

    def test_ambiguity_detection_low_confidence(self) -> None:
        """Test ambiguity detection with low confidence."""
        intent = AgentIntent(action="unknown", confidence=0.4)
        assert intent.is_ambiguous()

    def test_ambiguity_detection_high_alternatives(self) -> None:
        """Test ambiguity detection with high-probability alternatives."""
        intent = AgentIntent(
            action="create",
            confidence=0.5,
            alternatives=[("modify", 0.35), ("delete", 0.1)],
        )
        assert intent.is_ambiguous()

    def test_not_ambiguous(self) -> None:
        """Test non-ambiguous intent."""
        intent = AgentIntent(
            action="create",
            confidence=0.9,
            alternatives=[("modify", 0.05)],
        )
        assert not intent.is_ambiguous()


class TestAgentKnowledge:
    """Test AgentKnowledge dataclass."""

    def test_knowledge_overlap(self) -> None:
        """Test knowledge overlap calculation."""
        knowledge = AgentKnowledge(
            agent_id="test",
            known_topics={"python": 0.9, "pytorch": 0.8, "rust": 0.3},
        )

        # Full overlap
        overlap = knowledge.knowledge_overlap(["python", "pytorch"])
        assert overlap == 1.0

        # Partial overlap (rust confidence too low)
        overlap = knowledge.knowledge_overlap(["python", "rust"])
        assert overlap == 0.5

        # No overlap
        overlap = knowledge.knowledge_overlap(["unknown_topic"])
        assert overlap == 0.0

    def test_empty_topics(self) -> None:
        """Test overlap with empty topic list."""
        knowledge = AgentKnowledge(agent_id="test")
        overlap = knowledge.knowledge_overlap([])
        assert overlap == 1.0


class TestAgentState:
    """Test AgentState dataclass."""

    def test_basic_creation(self) -> None:
        """Test basic state creation."""
        state = AgentState(
            agent_id="test_user",
            agent_type=AgentType.USER,
        )
        assert state.agent_id == "test_user"
        assert state.agent_type == AgentType.USER
        assert state.beliefs == []
        assert state.interaction_count == 0

    def test_add_belief(self) -> None:
        """Test adding beliefs to state."""
        state = AgentState(agent_id="test")
        belief1 = AgentBelief(proposition="A is true", confidence=0.8)
        belief2 = AgentBelief(proposition="B is true", confidence=0.6)

        state.add_belief(belief1)
        state.add_belief(belief2)

        assert len(state.beliefs) == 2

    def test_update_existing_belief(self) -> None:
        """Test updating existing belief."""
        state = AgentState(agent_id="test")
        belief1 = AgentBelief(proposition="A is true", confidence=0.5)
        belief2 = AgentBelief(proposition="A is true", confidence=0.9)

        state.add_belief(belief1)
        state.add_belief(belief2)

        # Should update, not add duplicate
        assert len(state.beliefs) == 1
        assert state.beliefs[0].confidence == 0.9

    def test_get_belief(self) -> None:
        """Test retrieving belief by proposition."""
        state = AgentState(agent_id="test")
        belief = AgentBelief(proposition="A is true", confidence=0.8)
        state.add_belief(belief)

        found = state.get_belief("A is true")
        assert found is not None
        assert found.confidence == 0.8

        not_found = state.get_belief("B is true")
        assert not_found is None


# =============================================================================
# INTEGRATION TESTS
# =============================================================================


class TestAgentModelStateIntegration:
    """Test AgentModel and AgentState integration."""

    def test_update_state(self, agent_model: AgentModel) -> None:
        """Test updating model with state."""
        state = AgentState(
            agent_id="test_user",
            agent_type=AgentType.USER,
            e8_embedding=torch.randn(8),
        )
        agent_model.update_state(state)

        assert agent_model.current_state is not None
        assert agent_model.current_state.agent_id == "test_user"

    def test_state_persistence(self, agent_model: AgentModel) -> None:
        """Test that state persists across calls."""
        state = AgentState(agent_id="test", interaction_count=5)
        agent_model.update_state(state)

        # Run forward pass
        features = torch.randn(1, 64)
        _ = agent_model(features)

        # State should still be accessible
        assert agent_model.current_state.interaction_count == 5  # type: ignore[union-attr]


# =============================================================================
# ENUM TESTS
# =============================================================================


class TestEnums:
    """Test enum definitions."""

    def test_agent_types(self) -> None:
        """Test AgentType enum values."""
        assert AgentType.USER.value == "user"
        assert AgentType.AI_ASSISTANT.value == "ai"
        assert AgentType.COLONY.value == "colony"
        assert AgentType.EXTERNAL.value == "external"
        assert AgentType.UNKNOWN.value == "unknown"

    def test_confidence_levels(self) -> None:
        """Test ConfidenceLevel enum values."""
        assert ConfidenceLevel.CERTAIN.value == "certain"
        assert ConfidenceLevel.HIGH.value == "high"
        assert ConfidenceLevel.MEDIUM.value == "medium"
        assert ConfidenceLevel.LOW.value == "low"
        assert ConfidenceLevel.UNCERTAIN.value == "uncertain"
