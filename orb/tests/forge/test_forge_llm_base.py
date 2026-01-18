"""Tests for forge_llm_base module."""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.tier_integration


from kagami.forge.forge_llm_base import (
    CharacterAspect,
    CharacterContext,
    LLMRequest,
    LLMResponse,
    PromptTemplate,
    ReasoningStrategy,
)


class TestCharacterAspect:
    """Tests for CharacterAspect enum."""

    def test_all_aspects_exist(self) -> None:
        """Test all expected aspects exist."""
        assert CharacterAspect.VISUAL_DESIGN
        assert CharacterAspect.PERSONALITY
        assert CharacterAspect.VOICE
        assert CharacterAspect.MOTION
        assert CharacterAspect.BELIEFS
        assert CharacterAspect.BACKSTORY
        assert CharacterAspect.NARRATIVE_ROLE

    def test_aspect_values(self) -> None:
        """Test aspect values are strings."""
        for aspect in CharacterAspect:
            assert isinstance(aspect.value, str)


class TestReasoningStrategy:
    """Tests for ReasoningStrategy enum."""

    def test_all_strategies_exist(self) -> None:
        """Test all expected strategies exist."""
        assert ReasoningStrategy.MULTIMODAL
        assert ReasoningStrategy.INDUCTIVE
        assert ReasoningStrategy.CREATIVE
        assert ReasoningStrategy.ANALOGICAL
        assert ReasoningStrategy.DEDUCTIVE
        assert ReasoningStrategy.CAUSAL
        assert ReasoningStrategy.ABDUCTIVE

    def test_strategy_values(self) -> None:
        """Test strategy values are strings."""
        for strategy in ReasoningStrategy:
            assert isinstance(strategy.value, str)


class TestCharacterContext:
    """Tests for CharacterContext dataclass."""

    def test_creation_minimal(self) -> None:
        """Test creation with minimal args."""
        ctx = CharacterContext(
            character_id="char-123",
            name="Test Character",
        )

        assert ctx.character_id == "char-123"
        assert ctx.name == "Test Character"
        assert ctx.description == ""
        assert ctx.aspect == CharacterAspect.VISUAL_DESIGN
        assert ctx.metadata == {}

    def test_creation_full(self) -> None:
        """Test creation with all args."""
        ctx = CharacterContext(
            character_id="char-123",
            name="Test Character",
            description="A test description",
            aspect=CharacterAspect.PERSONALITY,
            metadata={"key": "value"},
        )

        assert ctx.description == "A test description"
        assert ctx.aspect == CharacterAspect.PERSONALITY
        assert ctx.metadata == {"key": "value"}

    def test_metadata_default_initialization(self) -> None:
        """Test metadata defaults to empty dict."""
        ctx = CharacterContext(
            character_id="char-123",
            name="Test",
            metadata=None,
        )

        assert ctx.metadata == {}


class TestLLMRequest:
    """Tests for LLMRequest dataclass."""

    def test_creation_minimal(self) -> None:
        """Test creation with minimal args."""
        req = LLMRequest(prompt="Generate something")

        assert req.prompt == "Generate something"
        assert req.context is None
        assert req.temperature == 0.5
        assert req.max_tokens == 500
        assert req.metadata == {}
        assert req.aspect is None
        assert req.require_json is False

    def test_creation_full(self) -> None:
        """Test creation with all args."""
        ctx = CharacterContext(character_id="c1", name="Test")
        req = LLMRequest(
            prompt="Generate",
            context=ctx,
            temperature=0.8,
            max_tokens=1000,
            metadata={"key": "value"},
            aspect=CharacterAspect.VOICE,
            require_json=True,
            template="voice_template",
        )

        assert req.context is ctx
        assert req.temperature == 0.8
        assert req.max_tokens == 1000
        assert req.aspect == CharacterAspect.VOICE
        assert req.require_json is True
        assert req.template == "voice_template"

    def test_metadata_default_initialization(self) -> None:
        """Test metadata defaults to empty dict."""
        req = LLMRequest(prompt="test", metadata=None)

        assert req.metadata == {}


class TestLLMResponse:
    """Tests for LLMResponse dataclass."""

    def test_creation_minimal(self) -> None:
        """Test creation with required args."""
        resp = LLMResponse(
            content="Generated content",
            model_name="test-model",
        )

        assert resp.content == "Generated content"
        assert resp.model_name == "test-model"
        assert resp.reasoning is None
        assert resp.confidence == 1.0
        assert resp.tokens_used == 0

    def test_creation_full(self) -> None:
        """Test creation with all args."""
        resp = LLMResponse(
            content="Generated content",
            reasoning="Because...",
            confidence=0.9,
            model_name="gpt-4",
            tokens_used=150,
        )

        assert resp.reasoning == "Because..."
        assert resp.confidence == 0.9
        assert resp.tokens_used == 150

    def test_creation_requires_model_name(self) -> None:
        """Test that model_name is required."""
        with pytest.raises(ValueError, match="model_name is required"):
            LLMResponse(content="test", model_name=None)


class TestPromptTemplate:
    """Tests for PromptTemplate dataclass."""

    def test_creation(self) -> None:
        """Test template creation."""
        template = PromptTemplate(
            template="Hello {name}, generate {item}",
            variables=["name", "item"],
            category="greeting",
        )

        assert "Hello" in template.template
        assert template.variables == ["name", "item"]
        assert template.category == "greeting"

    def test_format(self) -> None:
        """Test template formatting."""
        template = PromptTemplate(
            template="Generate a {style} character named {name}",
            variables=["style", "name"],
        )

        result = template.format(style="brave", name="Hero")

        assert result == "Generate a brave character named Hero"

    def test_default_category(self) -> None:
        """Test default category."""
        template = PromptTemplate(
            template="test",
            variables=[],
        )

        assert template.category == "general"
