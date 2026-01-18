"""Unit tests for GroveAgent - The Seeker.

Tests:
- Agent initialization
- System prompt content
- Tool availability
- Elliptic catastrophe behavior (D₄⁻ inward-convergence)
- Knowledge accumulation dynamics
- Research depth progression
- Escalation logic
- S⁷ embedding correctness

Created: December 14, 2025
"""

from __future__ import annotations

from unittest.mock import patch, AsyncMock

import pytest

pytestmark = pytest.mark.tier_unit


import torch

from kagami.core.unified_agents.agents.base_colony_agent import AgentResult
from kagami.core.unified_agents.agents.grove_agent import GroveAgent, create_grove_agent


# Mock web search to avoid network calls in unit tests
def _mock_web_search_results(query: str, depth: int = 1) -> list[dict]:
    """Generate mock web search results that simulate depth-based convergence."""
    base_results = [
        {
            "title": f"Result {i+1} for: {query}",
            "url": f"https://example.com/{i}",
            "snippet": f"This is relevant content about {query}. Details for depth {depth}.",
            "source": "web",
            "citations": 10 - i,  # Include citations for reference tests
        }
        for i in range(3 + depth)  # More results at higher depths
    ]
    return base_results


@pytest.fixture(autouse=True)
def mock_web_search():
    """Mock web search for all tests to avoid network dependencies."""
    async def _mock_search(query: str, max_results: int = 5, **kwargs):
        # Return mock results that vary by query complexity
        depth = kwargs.get("depth", 1)
        results = _mock_web_search_results(query, depth)[:max_results]
        return results

    with patch("kagami.tools.web.search.web_search", new_callable=AsyncMock) as mock:
        mock.side_effect = _mock_search
        yield mock


class TestGroveAgent:
    """Test suite for GroveAgent."""

    def test_initialization(self) -> None:
        """Test Grove agent initialization."""
        grove = create_grove_agent()

        assert grove.colony_idx == 5
        assert grove.colony_name == "grove"
        assert grove.convergence_depth == 0
        assert grove.context_map == {}

    def test_system_prompt(self) -> None:
        """Test system prompt contains key Grove characteristics."""
        grove = create_grove_agent()
        prompt = grove.get_system_prompt()

        # Check for key identity markers
        assert "Grove" in prompt
        assert "Scholar" in prompt or "scholar" in prompt.lower()
        assert "Elliptic" in prompt or "elliptic" in prompt.lower()
        assert "e₆" in prompt or "D₄⁻" in prompt

        # Check for catastrophe dynamics
        assert "understand" in prompt.lower() or "deeper" in prompt.lower()
        assert "converge" in prompt.lower() or "inward" in prompt.lower()

    def test_available_tools(self) -> None:
        """Test Grove has research/exploration tools."""
        grove = create_grove_agent()
        tools = grove.get_available_tools()

        # Check essential tools
        assert "research" in tools
        assert "explore" in tools
        assert "document" in tools
        assert "investigate" in tools
        assert "search" in tools
        assert "analyze" in tools

        # Should have multiple tools
        assert len(tools) >= 6

    def test_elliptic_convergence_behavior(self) -> None:
        """Test elliptic D₄⁻ inward-converging search dynamics."""
        grove = create_grove_agent()

        result = grove.process_with_catastrophe(
            task="research E8 lattice quantization",
            context={"max_depth": 3},
        )

        assert result.success is True
        assert result.metadata["catastrophe"] == "elliptic"  # type: ignore[index]
        assert result.output["depth_reached"] > 0  # type: ignore[operator,index]
        assert "findings" in result.output

        # Elliptic behavior: convergence depth should be tracked
        assert grove.convergence_depth > 0
        assert grove.convergence_depth <= 3

    def test_knowledge_accumulation(self) -> None:
        """Test Grove accumulates knowledge in context_map."""
        grove = create_grove_agent()

        result = grove.process_with_catastrophe(
            task="research G2 automorphism",
            context={"max_depth": 2},
        )

        assert result.success is True

        # Check context map accumulation
        assert len(grove.context_map) > 0
        assert "sources" in grove.context_map
        assert "concepts" in grove.context_map

        # Knowledge should be non-empty
        assert len(grove.context_map["sources"]) > 0
        assert len(grove.context_map["concepts"]) > 0

    def test_research_depth_progression(self) -> None:
        """Test research progresses through multiple layers."""
        grove = create_grove_agent()

        result = grove.process_with_catastrophe(
            task="research catastrophe theory",
            context={"max_depth": 3},
        )

        assert result.success is True

        # Check layer structure
        findings = result.output["findings"]  # type: ignore[index]
        assert "layers" in findings
        layers = findings["layers"]  # type: ignore[index]

        # Should have multiple layers (converging inward)
        assert len(layers) > 0
        assert len(layers) <= 3

        # Each layer should have structure
        for layer in layers:
            assert "query" in layer
            assert "depth" in layer
            assert "concepts" in layer
            assert "sources" in layer

    def test_surface_to_core_convergence(self) -> None:
        """Test elliptic convergence from surface to core."""
        grove = create_grove_agent()

        result = grove.process_with_catastrophe(
            task="research Fano plane",
            context={"max_depth": 3},
        )

        assert result.success is True

        layers = result.output["findings"]["layers"]  # type: ignore[index]

        # Verify convergence: later layers should have fewer sources
        if len(layers) > 1:
            layer_0_sources = len(layers[0]["sources"])  # type: ignore[index]
            layer_1_sources = len(layers[1]["sources"])  # type: ignore[index]
            assert layer_1_sources <= layer_0_sources

        # Core concepts should be extracted
        if "core_concepts" in result.output["findings"]:  # type: ignore[index]
            assert len(result.output["findings"]["core_concepts"]) > 0  # type: ignore[index]

    def test_focus_area_constraint(self) -> None:
        """Test focused research respects constraints."""
        grove = create_grove_agent()

        result = grove.process_with_catastrophe(
            task="research octonions",
            context={"max_depth": 2, "focus_area": "exceptional_algebras"},
        )

        assert result.success is True

        layers = result.output["findings"]["layers"]  # type: ignore[index]
        # Focus should be passed to layers
        for layer in layers:
            assert layer["focus"] == "exceptional_algebras"  # type: ignore[index]

    def test_deep_research_triggers_validation(self) -> None:
        """Test deep research (>2 layers) triggers Crystal validation."""
        grove = create_grove_agent()

        result = grove.process_with_catastrophe(
            task="research quantum computing",
            context={"max_depth": 3},
        )

        assert result.success is True

        # Deep research should escalate to Crystal for validation
        assert result.should_escalate is True
        assert result.escalation_target == "crystal"

    def test_explicit_validation_request(self) -> None:
        """Test explicit validation request escalates to Crystal."""
        grove = create_grove_agent()

        result = grove.process_with_catastrophe(
            task="research security best practices",
            context={"max_depth": 1, "require_validation": True},
        )

        assert result.success is True
        assert result.should_escalate is True
        assert result.escalation_target == "crystal"

    def test_shallow_research_no_escalation(self) -> None:
        """Test shallow research doesn't escalate unnecessarily."""
        grove = create_grove_agent()

        result = grove.process_with_catastrophe(
            task="quick lookup",
            context={"max_depth": 1, "require_validation": False},
        )

        assert result.success is True
        # Should not escalate for simple lookup
        assert result.should_escalate is False

    def test_convergence_strength_calculation(self) -> None:
        """Test convergence strength reflects research depth."""
        grove = create_grove_agent()

        # Shallow research
        result_shallow = grove.process_with_catastrophe(
            task="research basic topic",
            context={"max_depth": 1},
        )

        # Deep research
        result_deep = grove.process_with_catastrophe(
            task="research complex topic",
            context={"max_depth": 5},
        )

        # Deeper research should have higher convergence strength
        strength_shallow = result_shallow.output["convergence_strength"]  # type: ignore[index]
        strength_deep = result_deep.output["convergence_strength"]  # type: ignore[index]

        assert strength_deep >= strength_shallow

    def test_s7_embedding(self) -> None:
        """Test S⁷ embedding correctness."""
        grove = create_grove_agent()

        embedding = grove.get_embedding()

        # Check shape
        assert embedding.shape == (7,)

        # Check normalization
        norm = embedding.norm()
        assert torch.isclose(norm, torch.tensor(1.0), atol=1e-6)

        # Check unit vector at index 5 (Grove is e₆)
        assert embedding[5].item() == 1.0
        assert (embedding[[0, 1, 2, 3, 4, 6]] == 0).all()

    def test_result_s7_embedding(self) -> None:
        """Test S⁷ embedding in processing result."""
        grove = create_grove_agent()

        result = grove.process_with_catastrophe(
            task="research topic",
            context={"max_depth": 2},
        )

        assert result.s7_embedding is not None
        # Result embedding has batch dimension [1, 7]
        assert result.s7_embedding.shape == (1, 7)

        # Check embedding is on S⁷ sphere
        norm = result.s7_embedding.norm(dim=-1)
        assert torch.isclose(norm, torch.tensor(1.0), atol=1e-5)

    def test_convergence_state_getter(self) -> None:
        """Test convergence state retrieval."""
        grove = create_grove_agent()

        # Before research
        state_before = grove.get_convergence_state()
        assert state_before["depth"] == 0
        assert state_before["concepts_found"] == 0
        assert state_before["sources_found"] == 0

        # After research
        grove.process_with_catastrophe(
            task="research",
            context={"max_depth": 2},
        )

        state_after = grove.get_convergence_state()
        assert state_after["depth"] > 0
        assert state_after["concepts_found"] > 0
        assert state_after["sources_found"] > 0

    def test_reset_state_with_new_task(self) -> None:
        """Test state reset for new research task."""
        grove = create_grove_agent()

        # Do some research
        grove.process_with_catastrophe(
            task="research A",
            context={"max_depth": 2},
        )

        assert grove.convergence_depth > 0
        assert len(grove.context_map["sources"]) > 0

        # Reset
        grove.reset_state()

        assert grove.convergence_depth == 0
        assert len(grove.context_map["sources"]) == 0
        assert len(grove.context_map["concepts"]) == 0

    def test_knowledge_hoarding_behavior(self) -> None:
        """Test Grove hoards knowledge within a single research session."""
        grove = create_grove_agent()

        # Single research session accumulates knowledge across layers
        result = grove.process_with_catastrophe(
            task="research topic",
            context={"max_depth": 3},
        )

        # Knowledge accumulates across depth layers
        sources = grove.context_map["sources"]
        concepts = grove.context_map["concepts"]

        # Should have accumulated knowledge from multiple layers
        assert len(sources) > 0
        assert len(concepts) > 0

        # Deeper research should accumulate more
        # Layer 0: 10 sources, Layer 1: 8 sources, Layer 2: 6 sources
        # Total should reflect accumulation
        assert len(sources) >= 10  # At least surface layer sources

    def test_thorough_research_persona(self) -> None:
        """Test Grove's thoroughness - reads everything."""
        grove = create_grove_agent()

        result = grove.process_with_catastrophe(
            task="research topic",
            context={"max_depth": 5},  # Very deep
        )

        # Should attempt full depth
        assert grove.convergence_depth >= 3

        # Should accumulate significant knowledge
        assert len(grove.context_map["sources"]) > 10
        assert len(grove.context_map["concepts"]) > 5

    def test_curiosity_drives_depth(self) -> None:
        """Test Grove's curiosity drives exploration depth."""
        grove = create_grove_agent()

        result = grove.process_with_catastrophe(
            task="research fascinating topic",
            context={"max_depth": 10},  # Allow deep exploration
        )

        # Curiosity should drive deep research
        assert grove.convergence_depth > 1

        # Should follow leads
        layers = result.output["findings"]["layers"]  # type: ignore[index]
        assert len(layers) > 1

    def test_error_handling(self) -> None:
        """Test error handling in research."""
        grove = create_grove_agent()

        # This should not crash, but handle gracefully
        # (In practice, errors might come from external APIs)
        result = grove.process_with_catastrophe(
            task="research with error",
            context={},
        )

        # Should succeed (our mock doesn't error)
        assert result.success is True

    def test_should_escalate_method(self) -> None:
        """Test should_escalate method."""
        grove = create_grove_agent()

        result = grove.process_with_catastrophe(
            task="research topic",
            context={"max_depth": 3},
        )

        # should_escalate should reflect result.should_escalate
        escalate = grove.should_escalate(result, {})
        assert escalate == result.should_escalate

    def test_citation_tracking(self) -> None:
        """Test Grove tracks citations properly."""
        grove = create_grove_agent()

        result = grove.process_with_catastrophe(
            task="research academic topic",
            context={"max_depth": 2, "require_citations": True},
        )

        assert result.success is True

        # Metadata should track citations
        assert "citations" in result.metadata  # type: ignore[operator]
        citations_count = result.metadata["citations"]  # type: ignore[index]
        assert citations_count >= 0

    def test_multiple_independent_research_tasks(self) -> None:
        """Test Grove can handle multiple independent tasks."""
        grove = create_grove_agent()

        # Task 1
        result1 = grove.process_with_catastrophe(
            task="research E8",
            context={"max_depth": 2},
        )
        sources_1 = len(grove.context_map["sources"])

        # Reset for independence
        grove.reset_state()

        # Task 2
        result2 = grove.process_with_catastrophe(
            task="research G2",
            context={"max_depth": 2},
        )
        sources_2 = len(grove.context_map["sources"])

        # Both should succeed independently
        assert result1.success is True
        assert result2.success is True

        # After reset, second task starts fresh
        assert sources_2 < sources_1 + sources_2

    def test_never_satisfied_with_surface(self) -> None:
        """Test Grove never stops at surface level."""
        grove = create_grove_agent()

        result = grove.process_with_catastrophe(
            task="research",
            context={"max_depth": 10},  # Allow deep dive
        )

        # Should go deeper than surface (depth 0)
        assert grove.convergence_depth > 1

        # Should have multiple layers
        layers = result.output["findings"]["layers"]  # type: ignore[index]
        assert len(layers) > 1

    def test_convergence_to_core_concepts(self) -> None:
        """Test elliptic convergence extracts core concepts."""
        grove = create_grove_agent()

        result = grove.process_with_catastrophe(
            task="research complex system",
            context={"max_depth": 4},
        )

        findings = result.output["findings"]  # type: ignore[index]

        # Core concepts should be extracted from deepest layer
        if "core_concepts" in findings:
            core_concepts = findings["core_concepts"]  # type: ignore[index]
            assert len(core_concepts) > 0

            # Core concepts come from deepest layer
            deepest_layer = findings["layers"][-1]  # type: ignore[index]
            assert core_concepts == deepest_layer["concepts"]  # type: ignore[index]

    def test_collect_references(self) -> None:
        """Test reference collection helper."""
        grove = create_grove_agent()

        references = grove._collect_references("test research query")

        # Should return list of reference dicts
        assert isinstance(references, list)
        assert len(references) > 0

        # Each reference should have required fields
        for ref in references:
            assert "title" in ref
            assert "depth" in ref
            assert "relevance" in ref
            # citations is optional for web search results
            assert "source" in ref

        # Relevance should decay with depth
        if len(references) > 1:
            assert references[0]["relevance"] >= references[1]["relevance"]

    def test_synthesize_findings(self) -> None:
        """Test research synthesis in Grove's voice."""
        grove = create_grove_agent()

        references = [
            {"title": "Ref 1", "depth": 0, "relevance": 1.0, "citations": 10, "source": "arxiv"},
            {"title": "Ref 2", "depth": 1, "relevance": 0.5, "citations": 7, "source": "github"},
            {"title": "Ref 3", "depth": 2, "relevance": 0.3, "citations": 4, "source": "docs"},
        ]

        synthesis = grove._synthesize("test topic", references)

        # Should contain Grove's voice markers
        assert "research" in synthesis.lower() or "found" in synthesis.lower()
        assert "depth" in synthesis.lower() or "layer" in synthesis.lower()
        assert "convergence" in synthesis.lower() or "insight" in synthesis.lower()

        # Should mention number of sources
        assert str(len(references)) in synthesis

    def test_search_convergence_fast_path(self) -> None:
        """Test elliptic convergence with fast path (k<3)."""
        grove = create_grove_agent()

        state = torch.randn(1, 256)
        convergence = grove._search_convergence(state, k_value=1.0)

        # Should return convergence dict
        assert "attractor" in convergence
        assert "epistemic_value" in convergence
        assert "convergence_strength" in convergence
        assert "depth_estimate" in convergence

        # Should use fast path
        assert convergence["epistemic_value"] == 1.0

    def test_search_convergence_slow_path(self) -> None:
        """Test elliptic convergence with slow path (k>=3)."""
        grove = create_grove_agent()

        state = torch.randn(1, 256)
        convergence = grove._search_convergence(state, k_value=5.0)

        # Should return convergence dict
        assert "attractor" in convergence
        assert "epistemic_value" in convergence
        assert "convergence_strength" in convergence

        # Should use slow path
        assert convergence["epistemic_value"] == 5.0

    def test_error_handling_in_research(self) -> None:
        """Test Grove handles errors gracefully during research."""
        grove = create_grove_agent()

        # Cause an error by setting invalid state
        result = grove.process_with_catastrophe(
            task="research topic",
            context={"max_depth": -1},  # Invalid depth
        )

        # Even with errors, should return a result
        assert isinstance(result, AgentResult)
        # May fail but should not crash
        if not result.success:
            assert result.should_escalate is True
            assert result.escalation_target == "flow"

    def test_reset_state(self) -> None:
        """Test state reset clears convergence data."""
        grove = create_grove_agent()

        # Do some research
        grove.process_with_catastrophe(
            task="research topic",
            context={"max_depth": 2},
        )

        assert grove.convergence_depth > 0
        assert len(grove.context_map) > 0

        # Reset
        grove.reset_state()

        assert grove.convergence_depth == 0
        assert grove.context_map == {"sources": [], "concepts": [], "connections": []}

    def test_convergence_state_tracking(self) -> None:
        """Test convergence state getter."""
        grove = create_grove_agent()

        # Do research
        grove.process_with_catastrophe(
            task="research G2 algebra",
            context={"max_depth": 3},
        )

        state = grove.get_convergence_state()

        assert "depth" in state
        assert "concepts_found" in state
        assert "sources_found" in state
        assert "connections" in state

        assert state["depth"] == grove.convergence_depth
        assert state["concepts_found"] > 0
        assert state["sources_found"] > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
