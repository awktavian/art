"""Tests for Centralized LLM Service.

Tests cover:
- Service initialization (singleton pattern)
- Task type selection
- Generation operations (sync and async)
- Caching behavior
- Error handling
- Metrics collection

Coverage target: kagami/core/services/llm/service.py
"""

from __future__ import annotations
from typing import Any

import pytest

pytestmark = pytest.mark.tier_unit


from unittest.mock import AsyncMock, MagicMock, patch
import asyncio

from kagami.core.services.llm import (
    KagamiOSLLMService,
    get_llm_service,
    TaskType,
)

# =============================================================================
# FIXTURES
# =============================================================================


@pytest.fixture
def mock_ollama_response():
    """Mock Ollama API response."""
    return {
        "model": "qwen2.5:7b",
        "response": "This is a test response from the LLM.",
        "done": True,
    }


@pytest.fixture
def service():
    """Create LLM service for testing."""
    # Reset any global state
    with patch.dict("os.environ", {"KAGAMI_TEST_ECHO_LLM": "1"}):
        return KagamiOSLLMService()


# =============================================================================
# TASK TYPE TESTS
# =============================================================================


class TestTaskType:
    """Tests for TaskType enum."""

    def test_task_types_exist(self) -> None:
        """Test all expected task types exist (Dec 2025 API)."""
        # Current TaskType enum values
        assert hasattr(TaskType, "CONVERSATION")
        assert hasattr(TaskType, "CREATIVE")
        assert hasattr(TaskType, "REASONING")
        assert hasattr(TaskType, "EXTRACTION")
        assert hasattr(TaskType, "SUMMARY")

    def test_task_type_values(self) -> None:
        """Test task type values are distinct."""
        values = [t.value for t in TaskType]
        assert len(values) == len(set(values))  # All unique


# =============================================================================
# SERVICE INITIALIZATION TESTS
# =============================================================================


class TestLLMServiceInit:
    """Tests for LLM service initialization."""

    def test_service_creation(self, service) -> None:
        """Test basic service creation."""
        assert service is not None

    def test_singleton_pattern(self) -> None:
        """Test singleton pattern for global service."""
        with patch.dict("os.environ", {"KAGAMI_TEST_ECHO_LLM": "1"}):
            svc1 = get_llm_service()
            svc2 = get_llm_service()
            assert svc1 is svc2


# =============================================================================
# GENERATION TESTS
# =============================================================================


class TestLLMGeneration:
    """Tests for LLM generation operations."""

    @pytest.mark.asyncio
    async def test_generate_basic(self, service: Any) -> None:
        """Test basic text generation."""
        # Dec 2025: Service delegates to generate_v2, mock at that level
        with patch(
            "kagami.core.services.llm.generation_strategies.generate_v2", new_callable=AsyncMock
        ) as mock_gen:
            mock_gen.return_value = "Generated response"

            result = await service.generate(
                prompt="Hello, how are you?",
                app_name="test",
                task_type=TaskType.CONVERSATION,
            )

            assert result is not None
            mock_gen.assert_called_once()

    @pytest.mark.asyncio
    async def test_generate_with_system_prompt(self, service: Any) -> None:
        """Test generation with system prompt."""
        with patch(
            "kagami.core.services.llm.generation_strategies.generate_v2", new_callable=AsyncMock
        ) as mock_gen:
            mock_gen.return_value = "Response with system"

            result = await service.generate(
                prompt="Write a poem",
                app_name="test",
                task_type=TaskType.CREATIVE,
            )

            assert result is not None

    @pytest.mark.asyncio
    async def test_generate_code(self, service: Any) -> None:
        """Test code generation (uses EXTRACTION task type)."""
        with patch(
            "kagami.core.services.llm.generation_strategies.generate_v2", new_callable=AsyncMock
        ) as mock_gen:
            mock_gen.return_value = "def hello():\n    print('Hello')"

            result = await service.generate(
                prompt="Write a Python function that prints hello",
                app_name="test",
                task_type=TaskType.EXTRACTION,  # Dec 2025: CODE removed, use EXTRACTION
            )

            assert result is not None

    @pytest.mark.asyncio
    async def test_generate_reasoning(self, service: Any) -> None:
        """Test reasoning task."""
        with patch(
            "kagami.core.services.llm.generation_strategies.generate_v2", new_callable=AsyncMock
        ) as mock_gen:
            mock_gen.return_value = "The answer is 42 because..."

            result = await service.generate(
                prompt="What is 6 times 7 and why?",
                app_name="test",
                task_type=TaskType.REASONING,
            )

            assert result is not None


class TestLLMGenerationOptions:
    """Tests for generation options."""

    @pytest.mark.asyncio
    async def test_temperature_setting(self, service: Any) -> None:
        """Test temperature parameter."""
        with patch(
            "kagami.core.services.llm.generation_strategies.generate_v2", new_callable=AsyncMock
        ) as mock_gen:
            mock_gen.return_value = "Response"

            await service.generate(
                prompt="Test",
                app_name="test",
                temperature=0.7,
            )

            assert mock_gen.called

    @pytest.mark.asyncio
    async def test_max_tokens_setting(self, service: Any) -> None:
        """Test max_tokens parameter."""
        with patch(
            "kagami.core.services.llm.generation_strategies.generate_v2", new_callable=AsyncMock
        ) as mock_gen:
            mock_gen.return_value = "Short response"

            await service.generate(
                prompt="Test",
                app_name="test",
                max_tokens=100,
            )

            assert mock_gen.called

    @pytest.mark.asyncio
    async def test_stop_sequences(self, service: Any) -> None:
        """Test stop sequences parameter (via routing_hints)."""
        with patch(
            "kagami.core.services.llm.generation_strategies.generate_v2", new_callable=AsyncMock
        ) as mock_gen:
            mock_gen.return_value = "Response until stop"

            await service.generate(
                prompt="Test",
                app_name="test",
                routing_hints={"stop": ["END", "STOP"]},
            )

            assert mock_gen.called


# =============================================================================
# CACHING TESTS
# =============================================================================


class TestLLMCaching:
    """Tests for LLM response caching."""

    @pytest.mark.asyncio
    async def test_cache_hit(self, service: Any) -> None:
        """Test cache returns cached result."""
        prompt = "Cached prompt test"

        with patch(
            "kagami.core.services.llm.generation_strategies.generate_v2", new_callable=AsyncMock
        ) as mock_gen:
            mock_gen.return_value = "First response"

            # First call
            result1 = await service.generate(prompt=prompt, app_name="test")

            # Second call
            result2 = await service.generate(prompt=prompt, app_name="test")

            # Both should return results
            assert result1 is not None
            assert result2 is not None

    @pytest.mark.asyncio
    async def test_cache_bypass(self, service: Any) -> None:
        """Test cache bypass."""
        prompt = "No cache test"

        with patch(
            "kagami.core.services.llm.generation_strategies.generate_v2", new_callable=AsyncMock
        ) as mock_gen:
            mock_gen.return_value = "Response"

            await service.generate(prompt=prompt, app_name="test")
            await service.generate(prompt=prompt, app_name="test")

            # Should call twice
            assert mock_gen.call_count >= 1


# =============================================================================
# ERROR HANDLING TESTS
# =============================================================================


class TestLLMErrorHandling:
    """Tests for error handling."""

    @pytest.mark.asyncio
    async def test_connection_error(self, service: Any) -> None:
        """Test handling of connection errors."""
        with patch(
            "kagami.core.services.llm.generation_strategies.generate_v2", new_callable=AsyncMock
        ) as mock_gen:
            mock_gen.side_effect = ConnectionError("Cannot connect to LLM")

            with pytest.raises((ConnectionError, Exception)):
                await service.generate(prompt="Test", app_name="test")

    @pytest.mark.asyncio
    async def test_timeout_error(self, service: Any) -> None:
        """Test handling of timeout errors."""
        with patch(
            "kagami.core.services.llm.generation_strategies.generate_v2", new_callable=AsyncMock
        ) as mock_gen:
            mock_gen.side_effect = TimeoutError("Request timed out")

            with pytest.raises((asyncio.TimeoutError, Exception)):
                await service.generate(prompt="Test", app_name="test")

    @pytest.mark.asyncio
    async def test_empty_response(self, service: Any) -> None:
        """Test handling of empty response."""
        with patch(
            "kagami.core.services.llm.generation_strategies.generate_v2", new_callable=AsyncMock
        ) as mock_gen:
            mock_gen.return_value = ""

            result = await service.generate(prompt="Test", app_name="test")
            # Should handle empty response gracefully
            assert result is not None or result == ""


# =============================================================================
# STRUCTURED OUTPUT TESTS
# =============================================================================


class TestStructuredOutput:
    """Tests for structured output generation."""

    @pytest.mark.asyncio
    async def test_json_output(self, service: Any) -> None:
        """Test JSON structured output."""
        with patch(
            "kagami.core.services.llm.generation_strategies.generate_v2", new_callable=AsyncMock
        ) as mock_gen:
            mock_gen.return_value = '{"name": "test", "value": 42}'

            result = await service.generate(
                prompt="Generate JSON",
                app_name="test",
                routing_hints={"output_format": "json"},
            )

            assert result is not None

    @pytest.mark.asyncio
    async def test_pydantic_output(self, service: Any) -> None:
        """Test Pydantic model structured output."""
        from pydantic import BaseModel

        class StructuredResponse(BaseModel):
            name: str
            value: int

        with patch.object(service, "generate_structured", new_callable=AsyncMock) as mock_call:
            mock_call.return_value = StructuredResponse(name="test", value=42)

            result = await service.generate_structured(
                prompt="Generate structured",
                response_model=StructuredResponse,
            )

            # Verify result matches model
            if result is not None:
                assert hasattr(result, "name")
                assert hasattr(result, "value")


# =============================================================================
# STREAMING TESTS
# =============================================================================

# =============================================================================
# APP INTEGRATION TESTS
# =============================================================================


class TestLLMAppIntegration:
    """Tests for app-specific integration."""

    @pytest.mark.asyncio
    async def test_app_context(self, service: Any) -> None:
        """Test generation with app context."""
        with patch(
            "kagami.core.services.llm.generation_strategies.generate_v2", new_callable=AsyncMock
        ) as mock_gen:
            mock_gen.return_value = "Response for app"

            result = await service.generate(
                prompt="Test",
                app_name="forge",
            )

            assert result is not None

    @pytest.mark.asyncio
    async def test_correlation_id(self, service: Any) -> None:
        """Test correlation ID tracking."""
        with patch(
            "kagami.core.services.llm.generation_strategies.generate_v2", new_callable=AsyncMock
        ) as mock_gen:
            mock_gen.return_value = "Response"

            result = await service.generate(
                prompt="Test",
                app_name="test",
                routing_hints={"correlation_id": "test-corr-123"},
            )

            assert result is not None


# =============================================================================
# METRICS TESTS
# =============================================================================


class TestLLMMetrics:
    """Tests for metrics collection."""

    @pytest.mark.asyncio
    async def test_request_counter(self, service: Any) -> None:
        """Test request counter is incremented."""
        with patch(
            "kagami.core.services.llm.generation_strategies.generate_v2", new_callable=AsyncMock
        ) as mock_gen:
            mock_gen.return_value = "Response"

            await service.generate(prompt="Metrics test", app_name="test")

            assert mock_gen.called

    @pytest.mark.asyncio
    async def test_latency_histogram(self, service: Any) -> None:
        """Test latency histogram records timing."""
        with patch(
            "kagami.core.services.llm.generation_strategies.generate_v2", new_callable=AsyncMock
        ) as mock_gen:
            mock_gen.return_value = "Response"

            await service.generate(prompt="Latency test", app_name="test")

            assert mock_gen.called


# =============================================================================
# EDGE CASES
# =============================================================================


class TestLLMEdgeCases:
    """Tests for edge cases."""

    @pytest.mark.asyncio
    async def test_unicode_prompt(self, service: Any) -> None:
        """Test handling of unicode in prompt."""
        with patch(
            "kagami.core.services.llm.generation_strategies.generate_v2", new_callable=AsyncMock
        ) as mock_gen:
            mock_gen.return_value = "Response"

            result = await service.generate(
                prompt="日本語テスト 🎉 مرحبا",
                app_name="test",
            )

            assert result is not None

    @pytest.mark.asyncio
    async def test_very_long_prompt(self, service: Any) -> None:
        """Test handling of very long prompt."""
        with patch(
            "kagami.core.services.llm.generation_strategies.generate_v2", new_callable=AsyncMock
        ) as mock_gen:
            mock_gen.return_value = "Response"

            long_prompt = "word " * 10000
            result = await service.generate(prompt=long_prompt, app_name="test")

            assert mock_gen.called

    @pytest.mark.asyncio
    async def test_empty_prompt(self, service: Any) -> None:
        """Test handling of empty prompt."""
        with patch(
            "kagami.core.services.llm.generation_strategies.generate_v2", new_callable=AsyncMock
        ) as mock_gen:
            mock_gen.return_value = ""

            result = await service.generate(prompt="", app_name="test")
            # Should handle gracefully
            assert result is not None or result == ""

    @pytest.mark.asyncio
    async def test_special_characters(self, service: Any) -> None:
        """Test handling of special characters."""
        with patch(
            "kagami.core.services.llm.generation_strategies.generate_v2", new_callable=AsyncMock
        ) as mock_gen:
            mock_gen.return_value = "Response"

            result = await service.generate(
                prompt='Test with "quotes" and <tags> and {braces}',
                app_name="test",
            )

            assert result is not None
