"""Comprehensive tests for forge core_integration module.

Tests BaseComponent, ForgeComponent, CharacterResult, and related classes.
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.tier_integration


from kagami.forge.core_integration import (
    BaseComponent,
    CharacterAspect,
    CharacterContext,
    CharacterGenerationContext,
    CharacterResult,
    ForgeComponent,
    ForgeLLMAdapter,
    LLMRequest,
    LLMResponse,
    ProcessingStatus,
    ReasoningStrategy,
)


class TestBaseComponent:
    """Test BaseComponent class."""

    def test_creation(self) -> None:
        """Test creating a base component."""
        comp = BaseComponent("test_component")

        assert comp.name == "test_component"
        assert comp._initialized is False

    def test_initialize(self) -> None:
        """Test initializing a component."""
        comp = BaseComponent("test")
        comp.initialize()

        assert comp._initialized is True


class TestForgeComponent:
    """Test ForgeComponent class."""

    def test_creation_default_config(self) -> None:
        """Test creating with default config."""
        comp = ForgeComponent("test_forge")

        assert comp.name == "test_forge"
        assert comp.config == {}

    def test_creation_with_config(self) -> None:
        """Test creating with custom config."""
        config = {"param1": "value1", "param2": 42}
        comp = ForgeComponent("configured", config=config)

        assert comp.config == config

    def test_get_required_config_fields(self) -> None:
        """Test default required config fields."""
        comp = ForgeComponent("test")
        fields = comp._get_required_config_fields()

        assert fields == []

    def test_validate_config_specific(self) -> None:
        """Test default config validation."""
        comp = ForgeComponent("test")
        result = comp._validate_config_specific({})

        assert result is True

    def test_check_health(self) -> None:
        """Test default health check."""
        comp = ForgeComponent("test")
        result = comp._check_health()

        assert result is True

    def test_get_status_specific(self) -> None:
        """Test default status."""
        comp = ForgeComponent("test")
        status = comp._get_status_specific()

        assert status == {}


class TestCharacterAspect:
    """Test CharacterAspect enum."""

    def test_aspect_values(self) -> None:
        """Test all aspect values are defined."""
        assert CharacterAspect.VISUAL_DESIGN.value == "visual_design"
        assert CharacterAspect.PERSONALITY.value == "personality"
        assert CharacterAspect.VOICE.value == "voice"
        assert CharacterAspect.MOTION.value == "motion"
        assert CharacterAspect.BELIEFS.value == "beliefs"
        assert CharacterAspect.BACKSTORY.value == "backstory"
        assert CharacterAspect.NARRATIVE_ROLE.value == "narrative_role"


class TestProcessingStatus:
    """Test ProcessingStatus enum."""

    def test_status_values(self) -> None:
        """Test all status values are defined."""
        assert ProcessingStatus.PENDING.value == "pending"
        assert ProcessingStatus.PROCESSING.value == "processing"
        assert ProcessingStatus.COMPLETED.value == "completed"
        assert ProcessingStatus.FAILED.value == "failed"
        assert ProcessingStatus.OPTIMIZING.value == "optimizing"


class TestCharacterResult:
    """Test CharacterResult class."""

    def test_creation_minimal(self) -> None:
        """Test creating with minimal args."""
        result = CharacterResult(
            status=ProcessingStatus.COMPLETED,
            aspect=CharacterAspect.VISUAL_DESIGN,
            data={"mesh": "generated"},
        )

        assert result.status == ProcessingStatus.COMPLETED
        assert result.aspect == CharacterAspect.VISUAL_DESIGN
        assert result.data == {"mesh": "generated"}
        assert result.metadata == {}
        assert result.processing_time == 0.0
        assert result.quality_score == 0.0
        assert result.error is None

    def test_creation_full(self) -> None:
        """Test creating with all args."""
        result = CharacterResult(
            status=ProcessingStatus.FAILED,
            aspect=CharacterAspect.PERSONALITY,
            data=None,
            metadata={"attempt": 1},
            processing_time=5.5,
            quality_score=0.0,
            error="Generation failed",
        )

        assert result.status == ProcessingStatus.FAILED
        assert result.metadata == {"attempt": 1}
        assert result.processing_time == 5.5
        assert result.error == "Generation failed"


class TestLLMRequest:
    """Test LLMRequest class."""

    def test_creation(self) -> None:
        """Test creating an LLM request."""
        request = LLMRequest(
            aspect=CharacterAspect.PERSONALITY,
            prompt="Generate traits",
            context={"character_name": "Hero"},
        )

        assert request.aspect == CharacterAspect.PERSONALITY
        assert request.prompt == "Generate traits"
        assert request.context == {"character_name": "Hero"}
        assert request.template is None
        assert request.require_json is False

    def test_creation_with_options(self) -> None:
        """Test creating with template and json flag."""
        request = LLMRequest(
            aspect=CharacterAspect.VOICE,
            prompt="Generate voice profile",
            context={},
            template="voice_template.j2",
            require_json=True,
        )

        assert request.template == "voice_template.j2"
        assert request.require_json is True


class TestLLMResponse:
    """Test LLMResponse class."""

    def test_creation(self) -> None:
        """Test creating an LLM response."""
        response = LLMResponse(
            content="Generated content",
            reasoning="Because...",
            confidence=0.95,
            model_name="qwen3:7b",
            tokens_used=150,
        )

        assert response.content == "Generated content"
        assert response.reasoning == "Because..."
        assert response.confidence == 0.95
        assert response.model_name == "qwen3:7b"
        assert response.tokens_used == 150

    def test_creation_no_model_raises(self) -> None:
        """Test that missing model_name raises error."""
        with pytest.raises(ValueError, match="model_name is required"):
            LLMResponse(content="test", model_name=None)

    def test_creation_minimal(self) -> None:
        """Test creating with minimal args."""
        response = LLMResponse(content="test", model_name="test-model")

        assert response.reasoning is None
        assert response.confidence == 1.0
        assert response.tokens_used == 0


class TestReasoningStrategy:
    """Test ReasoningStrategy class (Enum)."""

    def test_strategy_values(self) -> None:
        """Test all strategy values."""
        assert ReasoningStrategy.MULTIMODAL.value == "multimodal"
        assert ReasoningStrategy.INDUCTIVE.value == "inductive"
        assert ReasoningStrategy.CREATIVE.value == "creative"
        assert ReasoningStrategy.ANALOGICAL.value == "analogical"
        assert ReasoningStrategy.DEDUCTIVE.value == "deductive"
        assert ReasoningStrategy.CAUSAL.value == "causal"
        assert ReasoningStrategy.ABDUCTIVE.value == "abductive"


class TestCharacterContext:
    """Test CharacterContext class (from forge_llm_base)."""

    def test_creation_minimal(self) -> None:
        """Test creating with minimal args."""
        ctx = CharacterContext(character_id="char-001", name="Hero")

        assert ctx.character_id == "char-001"
        assert ctx.name == "Hero"
        assert ctx.description == ""
        assert ctx.aspect == CharacterAspect.VISUAL_DESIGN  # default
        assert ctx.metadata == {}

    def test_creation_full(self) -> None:
        """Test creating with all args."""
        ctx = CharacterContext(
            character_id="char-002",
            name="Wise Mage",
            description="An ancient sorcerer",
            aspect=CharacterAspect.PERSONALITY,
            metadata={"genre": "fantasy"},
        )

        assert ctx.name == "Wise Mage"
        assert ctx.description == "An ancient sorcerer"
        assert ctx.aspect == CharacterAspect.PERSONALITY
        assert ctx.metadata == {"genre": "fantasy"}


class TestCharacterGenerationContext:
    """Test CharacterGenerationContext class (unique to core_integration)."""

    def test_creation_minimal(self) -> None:
        """Test creating with minimal args."""
        ctx = CharacterGenerationContext(character_id="char-001", concept="A brave warrior")

        assert ctx.character_id == "char-001"
        assert ctx.concept == "A brave warrior"
        assert ctx.personality_traits == []
        assert ctx.genre is None

    def test_creation_full(self) -> None:
        """Test creating with all args."""
        ctx = CharacterGenerationContext(
            character_id="char-002",
            concept="A wise mage",
            personality_traits=["intelligent", "calm"],
            genre="fantasy",
        )

        assert ctx.personality_traits == ["intelligent", "calm"]
        assert ctx.genre == "fantasy"


class TestForgeLLMAdapter:
    """Test ForgeLLMAdapter class."""

    def test_creation(self) -> None:
        """Test creating ForgeLLMAdapter."""
        llm = ForgeLLMAdapter()

        assert llm.config == {}
        assert llm._llm_instance is None

    def test_creation_with_config(self) -> None:
        """Test creating with config."""
        config = {"model_type": "qwen", "provider": "ollama"}
        llm = ForgeLLMAdapter(config=config)

        assert llm.config == config

    @pytest.mark.asyncio
    async def test_generate_not_initialized(self):
        """Test generate raises when not initialized."""
        llm = ForgeLLMAdapter()

        request = LLMRequest(aspect=CharacterAspect.PERSONALITY, prompt="test", context={})

        with pytest.raises(RuntimeError, match="LLM not initialized"):
            await llm.generate(request)
