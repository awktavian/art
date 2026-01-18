"""Tests for forge llm_service_adapter module."""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.tier_integration


from unittest.mock import Mock, patch, AsyncMock

from kagami.forge.llm_service_adapter import KagamiOSLLMServiceAdapter


class TestKagamiOSLLMServiceAdapter:
    """Tests for KagamiOSLLMServiceAdapter class."""

    def test_creation(self) -> None:
        """Test adapter creation."""
        adapter = KagamiOSLLMServiceAdapter()

        assert adapter is not None
        assert adapter._initialized is False
        assert adapter.llm_service is not None

    def test_creation_with_config(self) -> None:
        """Test adapter creation with config kwargs."""
        adapter = KagamiOSLLMServiceAdapter(model="test-model", temperature=0.5)

        assert adapter.config["model"] == "test-model"
        assert adapter.config["temperature"] == 0.5

    @pytest.mark.asyncio
    async def test_initialize(self):
        """Test initialize method."""
        adapter = KagamiOSLLMServiceAdapter()

        # Mock the underlying service
        adapter.llm_service.initialize = AsyncMock()  # type: ignore[method-assign]

        await adapter.initialize()

        assert adapter._initialized is True
        adapter.llm_service.initialize.assert_called_once()

    @pytest.mark.asyncio
    async def test_initialize_idempotent(self):
        """Test initialize is idempotent."""
        adapter = KagamiOSLLMServiceAdapter()
        adapter.llm_service.initialize = AsyncMock()  # type: ignore[method-assign]

        await adapter.initialize()
        await adapter.initialize()  # Should not call again

        adapter.llm_service.initialize.assert_called_once()

    @pytest.mark.asyncio
    async def test_generate(self):
        """Test generate method."""
        adapter = KagamiOSLLMServiceAdapter()
        adapter.llm_service.initialize = AsyncMock()  # type: ignore[method-assign]
        adapter.llm_service.generate = AsyncMock(return_value="Generated text")  # type: ignore[method-assign]

        result = await adapter.generate("Test prompt")

        assert result == "Generated text"
        adapter.llm_service.generate.assert_called_once()

    @pytest.mark.asyncio
    async def test_generate_with_params(self):
        """Test generate with custom parameters."""
        adapter = KagamiOSLLMServiceAdapter()
        adapter.llm_service.initialize = AsyncMock()  # type: ignore[method-assign]
        adapter.llm_service.generate = AsyncMock(return_value="Result")  # type: ignore[method-assign]

        result = await adapter.generate(
            "Test prompt",
            max_tokens=500,
            temperature=0.8,
        )

        assert result == "Result"
        # Verify params were passed
        call_kwargs = adapter.llm_service.generate.call_args[1]
        assert call_kwargs["max_tokens"] == 500
        assert call_kwargs["temperature"] == 0.8

    @pytest.mark.asyncio
    async def test_generate_text_alias(self):
        """Test generate_text is alias for generate."""
        adapter = KagamiOSLLMServiceAdapter()
        adapter.llm_service.initialize = AsyncMock()  # type: ignore[method-assign]
        adapter.llm_service.generate = AsyncMock(return_value="Text")  # type: ignore[method-assign]

        result = await adapter.generate_text("Prompt")

        assert result == "Text"

    @pytest.mark.asyncio
    async def test_reason_method(self):
        """Test reason method for LLMRequest compatibility."""
        adapter = KagamiOSLLMServiceAdapter()
        adapter.llm_service.initialize = AsyncMock()  # type: ignore[method-assign]
        adapter.llm_service.generate = AsyncMock(return_value="Reasoned response")  # type: ignore[method-assign]

        class MockRequest:
            prompt = "Reason about this"
            max_tokens = 500

        result = await adapter.reason(MockRequest())

        assert result.content == "Reasoned response"
        assert result.model_name == "kagami-llm"

    @pytest.mark.asyncio
    async def test_chat(self):
        """Test chat method."""
        adapter = KagamiOSLLMServiceAdapter()
        adapter.llm_service.initialize = AsyncMock()  # type: ignore[method-assign]
        adapter.llm_service.generate = AsyncMock(return_value="Chat response")  # type: ignore[method-assign]

        messages = [
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi there"},
            {"role": "user", "content": "How are you?"},
        ]

        result = await adapter.chat(messages)

        assert result == "Chat response"
        # Verify messages were concatenated
        call_kwargs = adapter.llm_service.generate.call_args[1]
        assert "user: Hello" in call_kwargs["prompt"]
        assert "assistant: Hi there" in call_kwargs["prompt"]

    @pytest.mark.asyncio
    async def test_analyze_content(self):
        """Test analyze_content method."""
        adapter = KagamiOSLLMServiceAdapter()
        adapter.llm_service.initialize = AsyncMock()  # type: ignore[method-assign]
        adapter.llm_service.generate = AsyncMock(return_value="Analysis result")  # type: ignore[method-assign]

        result = await adapter.analyze_content(
            content="Some text to analyze",
            task="Summarize the content",
        )

        assert isinstance(result, dict)
        assert result["task"] == "Summarize the content"
        assert result["analysis"] == "Analysis result"
        assert "confidence" in result
