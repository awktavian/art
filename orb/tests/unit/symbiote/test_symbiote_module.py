"""Tests for SymbioteModule (Theory of Mind orchestrator).

Validates:
1. Module initialization and configuration
2. Agent model management (create, get, evict)
3. Observation and inference pipeline
4. Social surprise computation (EFE integration)
5. Social safety computation (CBF integration)
6. Clarification and proactive assistance
7. Social context for routing

Created: December 21, 2025
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.tier_unit

import time

import torch

from kagami.core.symbiote import (
    AgentType,
    SymbioteConfig,
    SymbioteModule,
    create_symbiote_module,
    get_symbiote_module,
    reset_symbiote_module,
    set_symbiote_module,
)

# =============================================================================
# FIXTURES
# =============================================================================


@pytest.fixture(autouse=True)
def reset_singleton() -> None:
    """Reset singleton between tests."""
    reset_symbiote_module()


@pytest.fixture
def symbiote_config() -> SymbioteConfig:
    """Create test configuration."""
    return SymbioteConfig(
        max_agent_models=5,
        state_dim=32,
        e8_dim=8,
        hidden_dim=64,
        device="cpu",
    )


@pytest.fixture
def symbiote_module(symbiote_config: SymbioteConfig) -> SymbioteModule:
    """Create SymbioteModule for testing."""
    return create_symbiote_module(symbiote_config)


@pytest.fixture
def populated_module(symbiote_module: SymbioteModule) -> SymbioteModule:
    """Create module with some agents already registered."""
    symbiote_module.observe_agent_action("user_1", "open_project", {"project": "test"})
    symbiote_module.observe_agent_action("user_2", "run_test", {"test": "unit"})
    return symbiote_module


# =============================================================================
# INITIALIZATION TESTS
# =============================================================================


class TestSymbioteModuleInit:
    """Test SymbioteModule initialization."""

    def test_default_initialization(self) -> None:
        """Test initialization with default config."""
        module = SymbioteModule()
        assert module.config.max_agent_models == 32
        assert module.config.e8_dim == 8

    def test_custom_config(self, symbiote_config: SymbioteConfig) -> None:
        """Test initialization with custom config."""
        module = SymbioteModule(symbiote_config)
        assert module.config.max_agent_models == 5
        assert module.config.state_dim == 32

    def test_singleton_pattern(self) -> None:
        """Test singleton get/set/reset."""
        module1 = get_symbiote_module()
        module2 = get_symbiote_module()
        assert module1 is module2

        # Reset should clear
        reset_symbiote_module()
        module3 = get_symbiote_module()
        assert module3 is not module1

        # Set should replace
        custom = create_symbiote_module()
        set_symbiote_module(custom)
        assert get_symbiote_module() is custom


# =============================================================================
# AGENT MODEL MANAGEMENT TESTS
# =============================================================================


class TestAgentModelManagement:
    """Test agent model creation and management."""

    def test_get_or_create_agent_model(self, symbiote_module: SymbioteModule) -> None:
        """Test getting or creating agent models."""
        model1 = symbiote_module.get_or_create_agent_model("user_1", AgentType.USER)
        model2 = symbiote_module.get_or_create_agent_model("user_1", AgentType.USER)

        # Should return same model
        assert model1 is model2

    def test_different_agents(self, symbiote_module: SymbioteModule) -> None:
        """Test different agent IDs get different models."""
        model1 = symbiote_module.get_or_create_agent_model("user_1")
        model2 = symbiote_module.get_or_create_agent_model("user_2")

        assert model1 is not model2

    def test_eviction_when_full(self, symbiote_module: SymbioteModule) -> None:
        """Test LRU eviction when at capacity."""
        # Fill up to capacity (5 agents)
        for i in range(5):
            symbiote_module.observe_agent_action(f"user_{i}", "action")
            time.sleep(0.01)  # Ensure different timestamps

        # Verify all are tracked
        assert len(symbiote_module._agent_states) == 5

        # Add one more (should evict oldest)
        symbiote_module.observe_agent_action("user_new", "action")

        # Should still have 5 (evicted oldest)
        assert len(symbiote_module._agent_states) == 5
        # user_0 should be evicted (oldest)
        assert "user_0" not in symbiote_module._agent_states
        assert "user_new" in symbiote_module._agent_states

    def test_primary_user_not_evicted(self, symbiote_module: SymbioteModule) -> None:
        """Test that primary user is never evicted."""
        symbiote_module.set_primary_user("primary_user")

        # Fill up with other agents
        for i in range(6):
            symbiote_module.observe_agent_action(f"user_{i}", "action")
            time.sleep(0.01)

        # Primary user should still be tracked
        assert "primary_user" in symbiote_module._agent_states


# =============================================================================
# OBSERVATION & INFERENCE TESTS
# =============================================================================


class TestObservationInference:
    """Test observation and inference pipeline."""

    def test_observe_agent_action(self, symbiote_module: SymbioteModule) -> None:
        """Test basic action observation."""
        result = symbiote_module.observe_agent_action(
            agent_id="user_1",
            action="submit_query",
            context={"query": "how to build X"},
            agent_type=AgentType.USER,
        )

        assert result is not None
        assert "agent_id" in result
        assert "intent" in result
        assert "action_probs" in result
        assert "intent_confidence" in result

    def test_observation_updates_state(self, symbiote_module: SymbioteModule) -> None:
        """Test that observations update agent state."""
        symbiote_module.observe_agent_action("user_1", "action_1")
        symbiote_module.observe_agent_action("user_1", "action_2")

        state = symbiote_module._agent_states["user_1"]
        assert state.interaction_count == 2
        assert state.last_action == "action_2"
        assert "action_1" in state.action_history
        assert "action_2" in state.action_history

    def test_e8_embedding_updated(self, symbiote_module: SymbioteModule) -> None:
        """Test that E8 embedding is updated after observation."""
        symbiote_module.observe_agent_action("user_1", "test_action")

        state = symbiote_module._agent_states["user_1"]
        assert state.e8_embedding is not None
        assert state.e8_embedding.shape == (8,)

    def test_intent_inference(self, symbiote_module: SymbioteModule) -> None:
        """Test intent inference from actions."""
        result = symbiote_module.observe_agent_action(
            agent_id="user_1",
            action="create_file",
            context={"file": "main.py"},
        )

        intent = result["intent"]
        assert intent is not None
        assert intent.action == "create_file"
        assert intent.confidence > 0

    def test_anomaly_detection(self, symbiote_module: SymbioteModule) -> None:
        """Test anomaly detection in observations."""
        # Trigger low confidence (first observation)
        result = symbiote_module.observe_agent_action("user_1", "unknown_action")

        # Should detect some anomaly or low confidence
        assert "anomalies" in result
        assert isinstance(result["anomalies"], list)


# =============================================================================
# SOCIAL SURPRISE TESTS (EFE Integration)
# =============================================================================


class TestSocialSurprise:
    """Test social surprise computation for EFE."""

    def test_compute_social_surprise_no_agents(self, symbiote_module: SymbioteModule) -> None:
        """Test social surprise with no tracked agents."""
        action_embedding = torch.randn(1, 8)
        surprise = symbiote_module.compute_social_surprise(action_embedding)

        assert surprise.shape == (1,)
        # No agents = zero surprise
        assert surprise.item() == 0.0

    def test_compute_social_surprise_with_agents(self, populated_module: SymbioteModule) -> None:
        """Test social surprise with tracked agents."""
        action_embedding = torch.randn(1, 8)
        surprise = populated_module.compute_social_surprise(action_embedding)

        assert surprise.shape == (1,)
        assert surprise.item() >= 0  # Non-negative

    def test_batch_social_surprise(self, populated_module: SymbioteModule) -> None:
        """Test batched social surprise computation."""
        action_embedding = torch.randn(4, 8)
        surprise = populated_module.compute_social_surprise(action_embedding)

        assert surprise.shape == (4,)
        assert (surprise >= 0).all()

    def test_social_surprise_specific_agents(self, populated_module: SymbioteModule) -> None:
        """Test social surprise for specific agent subset."""
        action_embedding = torch.randn(1, 8)
        surprise = populated_module.compute_social_surprise(action_embedding, agent_ids=["user_1"])

        assert surprise.shape == (1,)


# =============================================================================
# SOCIAL SAFETY TESTS (CBF Integration)
# =============================================================================


class TestSocialSafety:
    """Test social safety computation for CBF."""

    def test_compute_social_safety_no_agents(self, symbiote_module: SymbioteModule) -> None:
        """Test social safety with no tracked agents."""
        action_embedding = torch.randn(1, 8)
        action_features = torch.randn(1, 32)
        safety = symbiote_module.compute_social_safety(action_embedding, action_features)

        # No agents = fully safe
        assert "social_h" in safety
        assert safety["social_h"].item() == 1.0
        assert safety["manipulation_safe"].item() == 1.0

    def test_compute_social_safety_with_agents(self, populated_module: SymbioteModule) -> None:
        """Test social safety with tracked agents."""
        action_embedding = torch.randn(1, 8)
        action_features = torch.randn(1, 32)
        safety = populated_module.compute_social_safety(action_embedding, action_features)

        assert "social_h" in safety
        assert "manipulation_safe" in safety
        assert "confusion_safe" in safety
        assert "harm_safe" in safety
        assert "alignment_safe" in safety

        # All values should be in [0, 1]
        for key in ["manipulation_safe", "confusion_safe", "harm_safe", "alignment_safe"]:
            val = safety[key].item()
            assert 0.0 <= val <= 1.0

    def test_batch_social_safety(self, populated_module: SymbioteModule) -> None:
        """Test batched social safety computation."""
        action_embedding = torch.randn(4, 8)
        action_features = torch.randn(4, 32)
        safety = populated_module.compute_social_safety(action_embedding, action_features)

        assert safety["social_h"].shape == (4,)


# =============================================================================
# CLARIFICATION & PROACTIVE ASSISTANCE TESTS
# =============================================================================


class TestClarificationAndAssistance:
    """Test clarification and proactive assistance features."""

    def test_should_clarify_no_agent(self, symbiote_module: SymbioteModule) -> None:
        """Test clarification check for unknown agent."""
        should_clarify, reason = symbiote_module.should_clarify("unknown_user")
        assert not should_clarify
        assert reason is None

    def test_should_clarify_after_ambiguous_observation(
        self, symbiote_module: SymbioteModule
    ) -> None:
        """Test clarification suggestion after ambiguous action."""
        # Make observation that might be ambiguous
        symbiote_module.observe_agent_action("user_1", "do_something")

        should_clarify, _reason = symbiote_module.should_clarify("user_1")
        # Result depends on inference confidence
        assert isinstance(should_clarify, bool)

    def test_suggest_clarification_question(self, symbiote_module: SymbioteModule) -> None:
        """Test clarification question generation."""
        symbiote_module.observe_agent_action("user_1", "ambiguous_action")

        question = symbiote_module.suggest_clarification_question("user_1")
        # May or may not generate question depending on confidence
        assert question is None or isinstance(question, str)

    def test_anticipate_needs(self, symbiote_module: SymbioteModule) -> None:
        """Test proactive needs anticipation."""
        symbiote_module.observe_agent_action("user_1", "debug", context={"error": "IndexError"})

        needs = symbiote_module.anticipate_needs("user_1")
        assert isinstance(needs, list)

    def test_anticipate_needs_unknown_agent(self, symbiote_module: SymbioteModule) -> None:
        """Test needs anticipation for unknown agent."""
        needs = symbiote_module.anticipate_needs("unknown")
        assert needs == []


# =============================================================================
# SOCIAL CONTEXT TESTS
# =============================================================================


class TestSocialContext:
    """Test social context aggregation for routing."""

    def test_get_social_context_empty(self, symbiote_module: SymbioteModule) -> None:
        """Test social context with no agents."""
        context = symbiote_module.get_social_context()

        assert context["has_active_agents"] is False
        assert context["social_complexity"] == 0.0
        assert context["clarification_needed"] is False

    def test_get_social_context_with_agents(self, populated_module: SymbioteModule) -> None:
        """Test social context with tracked agents."""
        context = populated_module.get_social_context()

        assert context["has_active_agents"] is True
        assert context["num_agents"] == 2
        assert "avg_intent_confidence" in context
        assert 0.0 <= context["social_complexity"] <= 1.0


# =============================================================================
# FORWARD PASS TESTS
# =============================================================================


class TestForwardPass:
    """Test nn.Module forward pass."""

    def test_forward_pass(self, populated_module: SymbioteModule) -> None:
        """Test forward pass returns all outputs."""
        action_embedding = torch.randn(1, 8)
        result = populated_module(action_embedding)

        assert "social_surprise" in result
        assert "social_h" in result
        assert "manipulation_safe" in result

    def test_forward_with_action_features(self, populated_module: SymbioteModule) -> None:
        """Test forward pass with explicit action features."""
        action_embedding = torch.randn(2, 8)
        action_features = torch.randn(2, 32)
        result = populated_module(action_embedding, action_features)

        assert result["social_surprise"].shape == (2,)
        assert result["social_h"].shape == (2,)


# =============================================================================
# CONFIGURATION TESTS
# =============================================================================


class TestSymbioteConfig:
    """Test SymbioteConfig dataclass."""

    def test_default_values(self) -> None:
        """Test default configuration values."""
        config = SymbioteConfig()

        assert config.max_agent_models == 32
        assert config.state_dim == 64
        assert config.e8_dim == 8
        assert config.social_surprise_weight == 0.3
        assert config.social_cbf_weight == 0.2

    def test_custom_values(self) -> None:
        """Test custom configuration."""
        config = SymbioteConfig(
            max_agent_models=100,
            social_surprise_weight=0.5,
            manipulation_threshold=0.9,
        )

        assert config.max_agent_models == 100
        assert config.social_surprise_weight == 0.5
        assert config.manipulation_threshold == 0.9
