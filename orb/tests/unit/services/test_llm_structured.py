"""Tests for LLM Structured Enhanced - covers EnhancedStructuredGenerator."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from kagami.core.services.llm.structured import (
    EnhancedStructuredGenerator,
    GenerationStrategy,
    GenerationResult,
    JSONRepairModule,
    SemanticValidator,
    get_enhanced_generator,
)


class TestLLMStructuredServiceInit:
    """Test EnhancedStructuredGenerator initialization."""

    def test_create_service(self) -> None:
        """Test creating the service."""
        service = EnhancedStructuredGenerator()
        assert service is not None
        assert hasattr(service, "repair_module")
        assert hasattr(service, "semantic_validator")
        assert hasattr(service, "feedback_store")

    def test_service_has_required_components(self) -> None:
        """Test service has required internal components."""
        service = EnhancedStructuredGenerator()
        assert isinstance(service.repair_module, JSONRepairModule)
        assert isinstance(service.semantic_validator, SemanticValidator)
        assert isinstance(service.feedback_store, list)
        assert isinstance(service.generation_history, dict)

    def test_get_enhanced_generator_singleton(self) -> None:
        """Test singleton accessor returns same instance."""
        gen1 = get_enhanced_generator()
        gen2 = get_enhanced_generator()
        assert gen1 is gen2


class TestJSONRepairModule:
    """Test JSON repair capabilities."""

    def test_regex_repairs_trailing_comma(self) -> None:
        """Test regex repairs fix trailing commas."""
        result = JSONRepairModule.regex_repairs('{"key": "value",}')
        assert result is not None
        assert result == '{"key": "value"}'

    def test_regex_repairs_trailing_comma_array(self) -> None:
        """Test regex repairs fix trailing commas in arrays."""
        result = JSONRepairModule.regex_repairs('["a", "b",]')
        assert result is not None
        assert result == '["a", "b"]'

    def test_tolerant_parse_valid_json(self) -> None:
        """Test tolerant parse with valid JSON."""
        result = JSONRepairModule.tolerant_parse('{"key": "value"}')
        assert result == {"key": "value"}

    def test_tolerant_parse_embedded_json(self) -> None:
        """Test tolerant parse extracts embedded JSON."""
        result = JSONRepairModule.tolerant_parse('Some text {"key": "value"} more text')
        assert result == {"key": "value"}

    def test_tolerant_parse_invalid_returns_none(self) -> None:
        """Test tolerant parse returns None for invalid JSON."""
        result = JSONRepairModule.tolerant_parse("not json at all")
        assert result is None


class TestGenerationStrategy:
    """Test generation strategy enum."""

    def test_strategy_values(self) -> None:
        """Test all strategy values exist."""
        assert GenerationStrategy.PROMPT_ONLY.value == "prompt_only"
        assert GenerationStrategy.GRAMMAR_CONSTRAINED.value == "grammar_constrained"
        assert GenerationStrategy.FUNCTION_CALLING.value == "function_calling"
        assert GenerationStrategy.SCRATCHPAD_REASONING.value == "scratchpad_reasoning"
        assert GenerationStrategy.INCREMENTAL_FIELDS.value == "incremental_fields"


class TestGenerationResult:
    """Test GenerationResult dataclass."""

    def test_create_success_result(self) -> None:
        """Test creating a success result."""
        result = GenerationResult(
            success=True,
            data={"key": "value"},
            strategy_used=GenerationStrategy.PROMPT_ONLY,
        )
        assert result.success is True
        assert result.data == {"key": "value"}
        assert result.strategy_used == GenerationStrategy.PROMPT_ONLY
        assert result.repair_applied is None
        assert result.error is None

    def test_create_failure_result(self) -> None:
        """Test creating a failure result."""
        result = GenerationResult(
            success=False,
            data=None,
            strategy_used=GenerationStrategy.GRAMMAR_CONSTRAINED,
            error="Timeout exceeded",
        )
        assert result.success is False
        assert result.data is None
        assert result.error == "Timeout exceeded"

    def test_result_with_reasoning_trace(self) -> None:
        """Test result with reasoning trace."""
        result = GenerationResult(
            success=True,
            data={"answer": 42},
            strategy_used=GenerationStrategy.SCRATCHPAD_REASONING,
            reasoning_trace="Step 1: Read the question...",
        )
        assert result.reasoning_trace is not None
        assert "Step 1" in result.reasoning_trace


class TestSemanticValidator:
    """Test semantic validation."""

    @pytest.mark.asyncio
    async def test_validate_timeline_valid(self):
        """Test timeline validation with valid dates."""
        data = {"start_date": "2025-01-01", "end_date": "2025-12-31"}
        valid, errors = await SemanticValidator.validate_timeline(data)
        assert valid is True
        assert len(errors) == 0

    @pytest.mark.asyncio
    async def test_validate_timeline_invalid_order(self):
        """Test timeline validation with end before start."""
        data = {"start_date": "2025-12-31", "end_date": "2025-01-01"}
        valid, errors = await SemanticValidator.validate_timeline(data)
        assert valid is False
        assert len(errors) > 0
        assert "before" in errors[0].lower()

    @pytest.mark.asyncio
    async def test_validate_financial_valid(self):
        """Test financial validation with valid amounts."""
        data = {"amount": 100.50, "percentage": 10}
        valid, errors = await SemanticValidator.validate_financial(data)
        assert valid is True
        assert len(errors) == 0

    @pytest.mark.asyncio
    async def test_validate_financial_negative_amount(self):
        """Test financial validation rejects negative amounts."""
        data = {"amount": -50}
        valid, errors = await SemanticValidator.validate_financial(data)
        assert valid is False
        assert any("negative" in e.lower() for e in errors)


class TestEnhancedGeneratorFallbackStrategies:
    """Test fallback strategy selection."""

    def test_get_fallback_strategies_from_prompt(self) -> None:
        """Test fallback strategies from prompt_only."""
        service = EnhancedStructuredGenerator()
        fallbacks = service._get_fallback_strategies(GenerationStrategy.PROMPT_ONLY)

        assert GenerationStrategy.GRAMMAR_CONSTRAINED in fallbacks
        assert len(fallbacks) > 0

    def test_get_fallback_strategies_from_grammar(self) -> None:
        """Test fallback strategies from grammar_constrained."""
        service = EnhancedStructuredGenerator()
        fallbacks = service._get_fallback_strategies(GenerationStrategy.GRAMMAR_CONSTRAINED)

        assert GenerationStrategy.SCRATCHPAD_REASONING in fallbacks

    def test_add_error_hints_json_error(self) -> None:
        """Test error hints for JSON decode errors."""
        service = EnhancedStructuredGenerator()
        prompt = "Generate JSON"
        enhanced = service._add_error_hints(prompt, "JSONDecodeError", None)

        assert "valid JSON" in enhanced
        assert len(enhanced) > len(prompt)

    def test_add_error_hints_validation_error(self) -> None:
        """Test error hints for validation errors."""
        service = EnhancedStructuredGenerator()
        prompt = "Generate data"
        enhanced = service._add_error_hints(prompt, "ValidationError: field required", None)

        assert "required fields" in enhanced


class TestGenerationHistory:
    """Test generation history tracking."""

    def test_generation_history_initialized(self) -> None:
        """Test generation history dict is initialized."""
        service = EnhancedStructuredGenerator()
        assert hasattr(service, "generation_history")
        assert isinstance(service.generation_history, dict)

    def test_feedback_store_initialized(self) -> None:
        """Test feedback store list is initialized."""
        service = EnhancedStructuredGenerator()
        assert hasattr(service, "feedback_store")
        assert isinstance(service.feedback_store, list)
        assert len(service.feedback_store) == 0
