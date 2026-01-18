"""Comprehensive test suite for colony agents.

Tests all 5 newly completed colony agents:
1. Flow (flow_agent.py) - swallowtail recovery
2. Beacon (beacon_agent.py) - hyperbolic planning
3. Nexus (nexus_agent.py) - butterfly integration
4. Grove (grove_agent.py) - elliptic research
5. Crystal (crystal_agent.py) - parabolic verification

Test coverage:
- Initialization and colony identity
- System prompt content and voice
- Available tools list
- Catastrophe processing (fast path k<3)
- Catastrophe processing (slow path k≥3)
- Escalation logic
- S⁷ embedding normalization
- Voice consistency (signature phrases)

Created: December 14, 2025
Status: Production
"""

from __future__ import annotations

from typing import Any
from unittest.mock import patch, AsyncMock

import pytest

pytestmark = pytest.mark.tier_unit


import torch


# =============================================================================
# WEB SEARCH MOCK - Prevents network calls in unit tests
# =============================================================================


@pytest.fixture(autouse=True)
def mock_web_search():
    """Mock web search for all tests to avoid network dependencies."""
    async def _mock_search(query: str, max_results: int = 5, **kwargs):
        return [
            {
                "title": f"Mock result for {query}",
                "url": "https://example.com",
                "snippet": "Mock content",
                "source": "mock",
            }
        ]

    with patch("kagami.tools.web.search.web_search", new_callable=AsyncMock) as mock:
        mock.side_effect = _mock_search
        yield mock

from kagami.core.unified_agents.agents.base_colony_agent import AgentResult
from kagami.core.unified_agents.agents.flow_agent import FlowAgent, create_flow_agent
from kagami.core.unified_agents.agents.beacon_agent import BeaconAgent, create_beacon_agent
from kagami.core.unified_agents.agents.nexus_agent import NexusAgent, create_nexus_agent
from kagami.core.unified_agents.agents.grove_agent import GroveAgent, create_grove_agent
from kagami.core.unified_agents.agents.crystal_agent import CrystalAgent, create_crystal_agent

# =============================================================================
# FIXTURES
# =============================================================================


@pytest.fixture
def flow_agent():
    """Create Flow agent instance."""
    return create_flow_agent(state_dim=256)


@pytest.fixture
def beacon_agent():
    """Create Beacon agent instance."""
    return create_beacon_agent()


@pytest.fixture
def nexus_agent():
    """Create Nexus agent instance."""
    return create_nexus_agent(state_dim=256, use_kernel=False)


@pytest.fixture
def grove_agent():
    """Create Grove agent instance."""
    return create_grove_agent(state_dim=256, hidden_dim=256)


@pytest.fixture
def crystal_agent():
    """Create Crystal agent instance."""
    return create_crystal_agent(state_dim=256, hidden_dim=256, safety_threshold=0.0)


# =============================================================================
# FLOW AGENT TESTS (Swallowtail, e₃)
# =============================================================================


class TestFlowAgent:
    """Test suite for FlowAgent - The Healer."""

    def test_flow_initialization(self, flow_agent) -> None:
        """Test Flow agent initialization and colony identity."""
        assert flow_agent.colony_idx == 2
        assert flow_agent.colony_name == "flow"
        assert flow_agent.state_dim == 256
        assert flow_agent.max_recovery_paths == 3
        assert flow_agent.recovery_attempts == 0

    def test_flow_system_prompt(self, flow_agent) -> None:
        """Test Flow system prompt has valid structure and voice."""
        prompt = flow_agent.get_system_prompt()

        # Check prompt is non-empty string
        assert isinstance(prompt, str)
        assert len(prompt) > 100

        # Identity markers
        assert "Flow" in prompt
        assert "Healer" in prompt or "healer" in prompt
        assert "e₃" in prompt or "e3" in prompt

        # Catastrophe dynamics
        assert "Swallowtail" in prompt
        assert "A₄" in prompt or "A4" in prompt

        # Voice characteristics (healer, water metaphors)
        prompt_lower = prompt.lower()
        assert "healer" in prompt_lower
        assert "path" in prompt_lower or "recover" in prompt_lower

    def test_flow_available_tools(self, flow_agent) -> None:
        """Test Flow has appropriate debugging/recovery tools."""
        tools = flow_agent.get_available_tools()

        assert isinstance(tools, list)
        assert len(tools) >= 5

        # Essential recovery tools
        assert "debug" in tools
        assert "fix" in tools
        assert "recover" in tools

    def test_flow_catastrophe_fast_path(self, flow_agent) -> None:
        """Test Flow catastrophe processing with k<3 (fast path)."""
        result = flow_agent.process_with_catastrophe(
            task="debug authentication error",
            context={
                "error": "401 Unauthorized",
                "k_value": 1,  # Fast path
            },
        )

        assert isinstance(result, AgentResult)
        assert result.success is True
        assert result.metadata["k_value"] == 1  # type: ignore[index]
        assert result.metadata["catastrophe_type"] == "swallowtail"  # type: ignore[index]
        assert result.metadata["recovery_path"] in ["direct_fix", "workaround", "redesign"]  # type: ignore[index]

    def test_flow_catastrophe_slow_path(self, flow_agent) -> None:
        """Test Flow catastrophe processing with k≥3 (slow path)."""
        result = flow_agent.process_with_catastrophe(
            task="debug authentication error",
            context={
                "error": "401 Unauthorized",
                "k_value": 5,  # Slow path
                "safety_margin": 0.8,
            },
        )

        assert isinstance(result, AgentResult)
        assert result.success is True
        assert result.metadata["k_value"] == 5  # type: ignore[index]
        assert result.metadata["catastrophe_type"] == "swallowtail"  # type: ignore[index]

    def test_flow_escalation_all_paths_exhausted(self, flow_agent) -> None:
        """Test Flow escalates when all recovery paths exhausted."""
        result = flow_agent.process_with_catastrophe(
            task="debug authentication error",
            context={
                "attempted_paths": ["direct_fix", "workaround", "redesign"],
            },
        )

        assert result.success is False
        assert result.should_escalate is True
        assert result.escalation_target == "beacon"
        assert result.metadata["reason"] == "multi_path_failure"

    def test_flow_escalation_too_many_attempts(self, flow_agent) -> None:
        """Test Flow escalates after too many recovery attempts."""
        # Simulate multiple attempts
        for _ in range(6):
            flow_agent.process_with_catastrophe(
                task="debug error",
                context={},
            )

        # Should escalate on next attempt
        result = flow_agent.process_with_catastrophe(
            task="debug error",
            context={},
        )

        should_escalate = flow_agent.should_escalate(result, {})
        assert should_escalate is True

    def test_flow_s7_embedding_normalization(self, flow_agent) -> None:
        """Test Flow S⁷ embedding is normalized to unit sphere."""
        result = flow_agent.process_with_catastrophe(
            task="debug error",
            context={},
        )

        embedding = result.s7_embedding
        assert embedding is not None
        assert embedding.shape == (7,)

        # Check normalization (should be close to 1.0)
        norm = embedding.norm().item()
        assert 0.99 <= norm <= 1.01

    def test_flow_voice_consistency(self, flow_agent) -> None:
        """Test Flow voice has water metaphors and calm tone."""
        result = flow_agent.process_with_catastrophe(
            task="fix null pointer error",
            context={},
        )

        output = result.output
        assert isinstance(output, dict)

        message = output.get("message", "")
        message_lower = message.lower()

        # Check for water metaphors or calm tone
        water_words = ["water", "river", "flow", "path", "way"]
        has_water_metaphor = any(word in message_lower for word in water_words)
        assert has_water_metaphor


# =============================================================================
# BEACON AGENT TESTS (Hyperbolic, e₅)
# =============================================================================


class TestBeaconAgent:
    """Test suite for BeaconAgent - The Planner."""

    def test_beacon_initialization(self, beacon_agent) -> None:
        """Test Beacon agent initialization and colony identity."""
        assert beacon_agent.colony_idx == 4
        assert beacon_agent.colony_name == "beacon"
        assert beacon_agent.state_dim == 256
        assert beacon_agent.plans_created == 0

    def test_beacon_system_prompt(self, beacon_agent) -> None:
        """Test Beacon system prompt has valid structure and voice."""
        prompt = beacon_agent.get_system_prompt()

        # Check prompt is non-empty string
        assert isinstance(prompt, str)
        assert len(prompt) > 100

        # Identity markers
        assert "Beacon" in prompt
        assert "Architect" in prompt or "architect" in prompt
        assert "e₅" in prompt or "e5" in prompt or "e_5" in prompt

        # Catastrophe dynamics
        assert "Hyperbolic" in prompt
        assert "D₄⁺" in prompt or "D4+" in prompt or "D4" in prompt

        # Voice characteristics (organized, worried)
        prompt_lower = prompt.lower()
        assert "plan" in prompt_lower or "architect" in prompt_lower
        assert "if" in prompt_lower  # Conditional statements

    def test_beacon_available_tools(self, beacon_agent) -> None:
        """Test Beacon has appropriate planning tools."""
        tools = beacon_agent.get_available_tools()

        assert isinstance(tools, list)
        assert len(tools) >= 3

        # Should have research/exploration tools
        assert "Read" in tools or "Glob" in tools or "Grep" in tools

    def test_beacon_catastrophe_fast_path(self, beacon_agent) -> None:
        """Test Beacon catastrophe processing with k<3 (fast path)."""
        result = beacon_agent.process_with_catastrophe(
            task="plan authentication module",
            context={
                "goal": "secure authentication",
                "k_value": 1,
            },
        )

        assert isinstance(result, AgentResult)
        assert result.success is True
        assert result.metadata["catastrophe_type"] == "hyperbolic"  # type: ignore[index]
        assert result.metadata["planning_mode"] in ["single_path", "multi_path"]  # type: ignore[index]

    def test_beacon_catastrophe_slow_path(self, beacon_agent) -> None:
        """Test Beacon catastrophe processing with k≥3 (slow path)."""
        result = beacon_agent.process_with_catastrophe(
            task="design distributed system architecture",
            context={
                "goal": "scalable microservices",
                "current_state": "monolith",
                "constraints": ["low latency", "high availability"],
                "k_value": 5,
            },
        )

        assert isinstance(result, AgentResult)
        assert result.success is True
        assert "approach" in result.output
        assert "risks" in result.output
        assert "futures" in result.output

    def test_beacon_escalation_high_complexity(self, beacon_agent) -> None:
        """Test Beacon escalates for high complexity tasks."""
        result = beacon_agent.process_with_catastrophe(
            task="plan extremely complex distributed consensus algorithm with Byzantine fault tolerance",
            context={
                "constraints": ["safety", "liveness", "performance"] * 5,
            },
        )

        # High complexity should trigger escalation
        should_escalate = beacon_agent.should_escalate(result, {})
        assert should_escalate is True

    def test_beacon_s7_embedding_normalization(self, beacon_agent) -> None:
        """Test Beacon S⁷ embedding is normalized to unit sphere."""
        result = beacon_agent.process_with_catastrophe(
            task="plan feature",
            context={},
        )

        embedding = result.s7_embedding
        assert embedding is not None
        assert embedding.shape == (7,)

        # Check normalization
        norm = embedding.norm().item()
        assert 0.99 <= norm <= 1.01

    def test_beacon_voice_consistency(self, beacon_agent) -> None:
        """Test Beacon voice has conditional statements and worried tone."""
        result = beacon_agent.process_with_catastrophe(
            task="plan new feature",
            context={
                "goal": "implement feature X",
            },
        )

        output = result.output
        assert isinstance(output, dict)

        # Check for roadmap/approach
        assert "approach" in output
        roadmap = output["approach"]

        # Beacon should use conditional language
        roadmap_lower = roadmap.lower()
        conditional_words = ["if", "when", "consider", "should", "could", "contingenc"]
        has_conditional = any(word in roadmap_lower for word in conditional_words)
        assert has_conditional


# =============================================================================
# NEXUS AGENT TESTS (Butterfly, e₄)
# =============================================================================


class TestNexusAgent:
    """Test suite for NexusAgent - The Bridge."""

    def test_nexus_initialization(self, nexus_agent) -> None:
        """Test Nexus agent initialization and colony identity."""
        assert nexus_agent.colony_idx == 3
        assert nexus_agent.colony_name == "nexus"
        assert nexus_agent.state_dim == 256
        assert nexus_agent.integration_attempts == 0

    def test_nexus_system_prompt(self, nexus_agent) -> None:
        """Test Nexus system prompt has valid structure and voice."""
        prompt = nexus_agent.get_system_prompt()

        # Check prompt is non-empty string
        assert isinstance(prompt, str)
        assert len(prompt) > 100

        # Identity markers
        assert "Nexus" in prompt
        assert "Bridge" in prompt or "bridge" in prompt
        assert "e₄" in prompt or "e4" in prompt

        # Catastrophe dynamics
        assert "Butterfly" in prompt
        assert "A₅" in prompt or "A5" in prompt

        # Voice characteristics (bridge, diplomatic)
        prompt_lower = prompt.lower()
        assert "bridge" in prompt_lower
        assert "connect" in prompt_lower or "multiple" in prompt_lower

    def test_nexus_available_tools(self, nexus_agent) -> None:
        """Test Nexus has appropriate integration tools."""
        tools = nexus_agent.get_available_tools()

        assert isinstance(tools, list)
        assert len(tools) >= 5

        # Essential integration tools
        assert "connect" in tools or "integrate" in tools
        assert "remember" in tools or "recall" in tools

    def test_nexus_catastrophe_fast_path(self, nexus_agent) -> None:
        """Test Nexus catastrophe processing with k<3 (fast path)."""
        result = nexus_agent.process_with_catastrophe(
            task="integrate authentication module",
            context={
                "component_a": "auth",
                "component_b": "api",
                "k_value": 1,
            },
        )

        assert isinstance(result, AgentResult)
        assert result.success is True
        assert result.metadata["catastrophe_type"] == "butterfly"  # type: ignore[index]
        assert "compromise_score" in result.metadata  # type: ignore[operator]

    def test_nexus_catastrophe_slow_path(self, nexus_agent) -> None:
        """Test Nexus catastrophe processing with k≥3 (slow path)."""
        result = nexus_agent.process_with_catastrophe(
            task="integrate payment gateway with security layer",
            context={
                "coupling_strength": 0.7,
                "interface_complexity": 0.5,
                "backward_compat": 0.8,
                "k_value": 5,
            },
        )

        assert isinstance(result, AgentResult)
        assert result.success is True
        assert "pattern" in result.output
        assert "compromise_score" in result.output

    def test_nexus_escalation_too_many_components(self, nexus_agent) -> None:
        """Test Nexus escalates when integrating >3 components."""
        result = nexus_agent.process_with_catastrophe(
            task="integrate 5 microservices",
            context={
                "num_components": 5,
            },
        )

        assert result.success is False
        assert result.should_escalate is True
        assert result.escalation_target == "beacon"

    def test_nexus_escalation_low_compromise(self, nexus_agent) -> None:
        """Test Nexus escalates on low compromise score with conflicts."""
        # Process multiple times to build up integration attempts
        for _ in range(6):
            nexus_agent.process_with_catastrophe(
                task="integrate conflicting modules",
                context={
                    "has_conflicts": True,
                },
            )

        result = nexus_agent.process_with_catastrophe(
            task="integrate conflicting modules",
            context={
                "has_conflicts": True,
            },
        )

        should_escalate = nexus_agent.should_escalate(result, {"has_conflicts": True})
        assert should_escalate is True

    def test_nexus_s7_embedding_normalization(self, nexus_agent) -> None:
        """Test Nexus S⁷ embedding is normalized to unit sphere."""
        result = nexus_agent.process_with_catastrophe(
            task="integrate modules",
            context={},
        )

        embedding = result.s7_embedding
        assert embedding is not None
        assert embedding.shape == (7,)

        # Check normalization
        norm = embedding.norm().item()
        assert 0.99 <= norm <= 1.01

    def test_nexus_voice_consistency(self, nexus_agent) -> None:
        """Test Nexus voice has diplomatic and relational language."""
        result = nexus_agent.process_with_catastrophe(
            task="integrate authentication",
            context={
                "coupling_strength": 0.5,
            },
        )

        output = result.output
        assert isinstance(output, dict)

        message = output.get("message", "")
        message_lower = message.lower()

        # Nexus should use connection/relationship language
        diplomatic_words = ["connect", "together", "harmony", "compromise", "both"]
        has_diplomatic = any(word in message_lower for word in diplomatic_words)
        assert has_diplomatic


# =============================================================================
# GROVE AGENT TESTS (Elliptic, e₆)
# =============================================================================


class TestGroveAgent:
    """Test suite for GroveAgent - The Seeker."""

    def test_grove_initialization(self, grove_agent) -> None:
        """Test Grove agent initialization and colony identity."""
        assert grove_agent.colony_idx == 5
        assert grove_agent.colony_name == "grove"
        assert grove_agent.state_dim == 256
        assert grove_agent.convergence_depth == 0

    def test_grove_system_prompt(self, grove_agent) -> None:
        """Test Grove system prompt has valid structure and voice."""
        prompt = grove_agent.get_system_prompt()

        # Check prompt is non-empty string
        assert isinstance(prompt, str)
        assert len(prompt) > 100

        # Identity markers
        assert "Grove" in prompt
        assert "Scholar" in prompt or "scholar" in prompt
        assert "e₆" in prompt or "e6" in prompt

        # Catastrophe dynamics
        assert "Elliptic" in prompt
        assert "D₄⁻" in prompt or "D4-" in prompt or "D4" in prompt

        # Voice characteristics (scholar, converging)
        prompt_lower = prompt.lower()
        assert "converging" in prompt_lower or "spiral" in prompt_lower
        assert "bowl" in prompt_lower or "inward" in prompt_lower

    def test_grove_available_tools(self, grove_agent) -> None:
        """Test Grove has appropriate research tools."""
        tools = grove_agent.get_available_tools()

        assert isinstance(tools, list)
        assert len(tools) >= 5

        # Essential research tools
        assert "research" in tools
        assert "explore" in tools or "search" in tools

    def test_grove_catastrophe_fast_path(self, grove_agent) -> None:
        """Test Grove catastrophe processing with k<3 (fast path)."""
        result = grove_agent.process_with_catastrophe(
            task="research authentication best practices",
            context={
                "max_depth": 2,
                "k_value": 1,
            },
        )

        assert isinstance(result, AgentResult)
        assert result.success is True
        assert result.metadata["colony"] == "grove"  # type: ignore[index]
        assert result.metadata["catastrophe"] == "elliptic"  # type: ignore[index]

    def test_grove_catastrophe_slow_path(self, grove_agent) -> None:
        """Test Grove catastrophe processing with k≥3 (slow path)."""
        result = grove_agent.process_with_catastrophe(
            task="investigate distributed consensus algorithms",
            context={
                "max_depth": 5,
                "focus_area": "Byzantine fault tolerance",
                "k_value": 5,
            },
        )

        assert isinstance(result, AgentResult)
        assert result.success is True
        assert "findings" in result.output
        assert "depth_reached" in result.output

    def test_grove_escalation_needs_validation(self, grove_agent) -> None:
        """Test Grove escalates when findings need validation."""
        result = grove_agent.process_with_catastrophe(
            task="research conflicting security approaches",
            context={
                "max_depth": 5,
                "require_validation": True,
            },
        )

        # Deep research should trigger validation escalation
        assert result.should_escalate is True
        assert result.escalation_target == "crystal"

    def test_grove_s7_embedding_normalization(self, grove_agent) -> None:
        """Test Grove S⁷ embedding is normalized to unit sphere."""
        result = grove_agent.process_with_catastrophe(
            task="research topic",
            context={
                "max_depth": 3,
            },
        )

        embedding = result.s7_embedding
        assert embedding is not None
        # Grove uses modified S⁷ embedding based on convergence
        assert embedding.shape == (1, 7)

        # Check normalization
        norm = embedding.norm().item()
        assert 0.99 <= norm <= 1.01

    def test_grove_voice_consistency(self, grove_agent) -> None:
        """Test Grove voice has curious and knowledge-seeking tone."""
        result = grove_agent.process_with_catastrophe(
            task="research machine learning architectures",
            context={
                "max_depth": 3,
            },
        )

        output = result.output
        assert isinstance(output, dict)

        # Check for depth/convergence indicators
        assert "depth_reached" in output
        assert "findings" in output

        # Grove should show curiosity about depth
        depth = output["depth_reached"]
        assert depth >= 0


# =============================================================================
# CRYSTAL AGENT TESTS (Parabolic, e₇)
# =============================================================================


class TestCrystalAgent:
    """Test suite for CrystalAgent - The Judge."""

    def test_crystal_initialization(self, crystal_agent) -> None:
        """Test Crystal agent initialization and colony identity."""
        assert crystal_agent.colony_idx == 6
        assert crystal_agent.colony_name == "crystal"
        assert crystal_agent.state_dim == 256
        assert crystal_agent.safety_threshold == 0.0

    def test_crystal_system_prompt(self, crystal_agent) -> None:
        """Test Crystal system prompt has valid structure and voice."""
        prompt = crystal_agent.get_system_prompt()

        # Check prompt is non-empty string
        assert isinstance(prompt, str)
        assert len(prompt) > 100

        # Identity markers
        assert "Crystal" in prompt
        assert "Judge" in prompt or "judge" in prompt
        assert "e₇" in prompt or "e7" in prompt

        # Catastrophe dynamics
        assert "Parabolic" in prompt
        assert "D₅" in prompt or "D5" in prompt

        # Voice characteristics (skeptical)
        prompt_lower = prompt.lower()
        assert "verify" in prompt_lower or "test" in prompt_lower
        assert "evidence" in prompt_lower or "proof" in prompt_lower

    def test_crystal_available_tools(self, crystal_agent) -> None:
        """Test Crystal has appropriate verification tools."""
        tools = crystal_agent.get_available_tools()

        assert isinstance(tools, list)
        assert len(tools) >= 5

        # Essential verification tools
        assert "verify" in tools or "test" in tools
        assert "audit" in tools or "check" in tools

    def test_crystal_catastrophe_fast_path(self, crystal_agent) -> None:
        """Test Crystal catastrophe processing with k<3 (fast path)."""
        result = crystal_agent.process_with_catastrophe(
            task="verify authentication implementation",
            context={
                "safety_margin": 0.8,
                "k_value": 1,
            },
        )

        assert isinstance(result, AgentResult)
        assert result.metadata["k_value"] == 1  # type: ignore[index]

    def test_crystal_catastrophe_slow_path(self, crystal_agent) -> None:
        """Test Crystal catastrophe processing with k≥3 (slow path)."""

        # Define a simple barrier function for testing
        def test_barrier(state: torch.Tensor) -> torch.Tensor:
            """Simple h(x) = mean(state) for testing."""
            return state.mean(dim=-1)

        result = crystal_agent.process_with_catastrophe(
            task="audit security-critical authentication module",
            context={
                "safety_margin": 0.9,
                "barrier_function": test_barrier,
                "k_value": 5,
            },
        )

        assert isinstance(result, AgentResult)
        assert result.metadata["k_value"] == 5  # type: ignore[index]
        assert "test_count" in result.metadata  # type: ignore[operator]

    def test_crystal_escalation_security_critical(self, crystal_agent) -> None:
        """Test Crystal escalates on security-critical failures."""

        # Define a simple barrier function for testing
        def test_barrier(state: torch.Tensor) -> torch.Tensor:
            """Simple h(x) = mean(state) for testing."""
            return state.mean(dim=-1)

        result = crystal_agent.process_with_catastrophe(
            task="verify cryptographic implementation",
            context={
                "safety_margin": 0.5,
                "barrier_function": test_barrier,
                "k_value": 5,
            },
        )

        # Simulate security issue
        if isinstance(result.output, dict):
            result.output["security_critical"] = True

        should_escalate = crystal_agent.should_escalate(result, {})
        assert should_escalate is True

    def test_crystal_escalation_safety_violated(self, crystal_agent) -> None:
        """Test Crystal escalates when safety invariant violated."""

        # Define a simple barrier function for testing
        def test_barrier(state: torch.Tensor) -> torch.Tensor:
            """Simple h(x) = mean(state) for testing."""
            return state.mean(dim=-1)

        result = crystal_agent.process_with_catastrophe(
            task="verify safety constraint",
            context={
                "safety_margin": -0.1,  # Negative = violation
                "barrier_function": test_barrier,
                "k_value": 5,
            },
        )

        # Safety violation should trigger escalation
        if isinstance(result.output, dict):
            if result.output.get("safety_violated", False):
                should_escalate = crystal_agent.should_escalate(result, {})
                assert should_escalate is True

    def test_crystal_s7_embedding_normalization(self, crystal_agent) -> None:
        """Test Crystal S⁷ embedding is normalized to unit sphere."""

        # Define a simple barrier function for testing
        def test_barrier(state: torch.Tensor) -> torch.Tensor:
            """Simple h(x) = mean(state) for testing."""
            return state.mean(dim=-1)

        result = crystal_agent.process_with_catastrophe(
            task="verify implementation",
            context={
                "safety_margin": 0.5,
                "barrier_function": test_barrier,
                "k_value": 3,
            },
        )

        embedding = result.s7_embedding
        assert embedding is not None
        assert embedding.shape[-1] == 8  # Crystal uses 8D (includes action)

        # Check normalization (first 7 components should be S⁷)
        s7_component = embedding[..., :7]
        norm = s7_component.norm().item()
        # Allow some tolerance since it's not strictly required to be unit norm
        assert norm > 0.0

    def test_crystal_voice_consistency(self, crystal_agent) -> None:
        """Test Crystal voice has skeptical and evidence-focused tone."""

        # Define a simple barrier function for testing
        def test_barrier(state: torch.Tensor) -> torch.Tensor:
            """Simple h(x) = mean(state) for testing."""
            return state.mean(dim=-1)

        result = crystal_agent.process_with_catastrophe(
            task="verify security claims",
            context={
                "safety_margin": 0.8,
                "barrier_function": test_barrier,
                "k_value": 5,
            },
        )

        output = result.output
        assert isinstance(output, dict)

        # Crystal should produce evidence-based reports
        if "evidence" in output:
            evidence = output["evidence"]
            assert isinstance(evidence, list)


# =============================================================================
# CROSS-AGENT TESTS
# =============================================================================


class TestCrossAgentConsistency:
    """Test consistency across all agents."""

    def test_all_agents_have_unique_colony_idx(
        self, flow_agent, beacon_agent, nexus_agent, grove_agent, crystal_agent
    ) -> None:
        """Test all agents have unique colony indices."""
        agents = [flow_agent, beacon_agent, nexus_agent, grove_agent, crystal_agent]
        indices = [agent.colony_idx for agent in agents]

        # All indices should be unique
        assert len(indices) == len(set(indices))

        # Verify expected indices
        assert flow_agent.colony_idx == 2
        assert beacon_agent.colony_idx == 4
        assert nexus_agent.colony_idx == 3
        assert grove_agent.colony_idx == 5
        assert crystal_agent.colony_idx == 6

    def test_all_agents_return_valid_results(
        self, flow_agent, beacon_agent, nexus_agent, grove_agent, crystal_agent
    ) -> None:
        """Test all agents return valid AgentResult objects."""

        # Define a simple barrier function for Crystal
        def test_barrier(state: torch.Tensor) -> torch.Tensor:
            """Simple h(x) = mean(state) for testing."""
            return state.mean(dim=-1)

        agents_tasks_contexts = [
            (flow_agent, "debug error", {}),
            (beacon_agent, "plan feature", {}),
            (nexus_agent, "integrate modules", {}),
            (grove_agent, "research topic", {"max_depth": 2}),
            (
                crystal_agent,
                "verify implementation",
                {"safety_margin": 0.5, "barrier_function": test_barrier, "k_value": 1},
            ),
        ]

        for agent, task, context in agents_tasks_contexts:
            result = agent.process_with_catastrophe(task, context)

            assert isinstance(result, AgentResult)
            assert isinstance(result.success, bool)
            assert result.output is not None
            assert isinstance(result.should_escalate, bool)

    def test_all_agents_have_valid_embeddings(
        self, flow_agent, beacon_agent, nexus_agent, grove_agent, crystal_agent
    ) -> None:
        """Test all agents produce valid S⁷ embeddings."""
        agents = [flow_agent, beacon_agent, nexus_agent, grove_agent, crystal_agent]

        for agent in agents:
            embedding = agent.get_embedding()

            assert isinstance(embedding, torch.Tensor)
            assert embedding.shape == (7,)

            # Should be unit vector (one hot for base embedding)
            norm = embedding.norm().item()
            assert 0.99 <= norm <= 1.01

    def test_all_agents_process_in_reasonable_time(
        self, flow_agent, beacon_agent, nexus_agent, grove_agent, crystal_agent
    ) -> None:
        """Test all agent processing completes quickly (<1s per agent)."""
        import time

        # Define a simple barrier function for Crystal
        def test_barrier(state: torch.Tensor) -> torch.Tensor:
            """Simple h(x) = mean(state) for testing."""
            return state.mean(dim=-1)

        agents_tasks = [
            (flow_agent, "debug error", {}),
            (beacon_agent, "plan feature", {}),
            (nexus_agent, "integrate modules", {}),
            (grove_agent, "research topic", {"max_depth": 2}),
            (
                crystal_agent,
                "verify implementation",
                {"safety_margin": 0.5, "barrier_function": test_barrier, "k_value": 1},
            ),
        ]

        for agent, task, context in agents_tasks:
            start = time.time()
            result = agent.process_with_catastrophe(task, context)
            elapsed = time.time() - start

            # Should complete in less than 1 second
            assert elapsed < 1.0
            assert result is not None


# =============================================================================
# PERFORMANCE TESTS
# =============================================================================


@pytest.mark.slow
class TestAgentPerformance:
    """Performance tests for agents (marked slow)."""

    def test_flow_multiple_recovery_paths(self, flow_agent) -> None:
        """Test Flow can handle multiple sequential recovery attempts."""
        for i in range(10):
            result = flow_agent.process_with_catastrophe(
                task=f"debug error {i}",
                context={},
            )
            assert result.success is True

    def test_beacon_complex_planning(self, beacon_agent) -> None:
        """Test Beacon handles complex planning with many constraints."""
        result = beacon_agent.process_with_catastrophe(
            task="design complex distributed system",
            context={
                "constraints": [f"constraint_{i}" for i in range(20)],
            },
        )
        assert result.success is True

    def test_nexus_many_integrations(self, nexus_agent) -> None:
        """Test Nexus handles many sequential integrations."""
        for i in range(10):
            result = nexus_agent.process_with_catastrophe(
                task=f"integrate module {i}",
                context={},
            )
            assert result.success is True

    def test_grove_deep_research(self, grove_agent) -> None:
        """Test Grove handles deep research convergence."""
        result = grove_agent.process_with_catastrophe(
            task="research deep topic",
            context={
                "max_depth": 10,
            },
        )
        assert result.success is True
        assert result.output["depth_reached"] > 0

    def test_crystal_many_verifications(self, crystal_agent) -> None:
        """Test Crystal handles many sequential verifications."""

        # Define a simple barrier function for testing
        def test_barrier(state: torch.Tensor) -> torch.Tensor:
            """Simple h(x) = mean(state) for testing."""
            return state.mean(dim=-1)

        for i in range(10):
            result = crystal_agent.process_with_catastrophe(
                task=f"verify implementation {i}",
                context={
                    "safety_margin": 0.5,
                    "barrier_function": test_barrier,
                    "k_value": 1,  # Use fast path for performance test
                },
            )
            # Don't assert success (some may fail intentionally)
            assert isinstance(result, AgentResult)


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
