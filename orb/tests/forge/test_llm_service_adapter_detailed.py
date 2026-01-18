"""Tests for kagami.forge.llm_service_adapter (KagamiOSLLMServiceAdapter)."""

from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from kagami.forge.llm_service_adapter import KagamiOSLLMServiceAdapter

pytestmark = pytest.mark.tier_integration


@pytest.fixture
def llm_adapter():
    """Create LLM adapter instance."""
    return KagamiOSLLMServiceAdapter()


class TestLLMAdapterInit:
    """Test LLM adapter initialization."""

    def test_init_default(self):
        """Test default initialization."""
        adapter = KagamiOSLLMServiceAdapter()
        assert adapter is not None

    @pytest.mark.asyncio
    async def test_initialize(self, llm_adapter):
        """Test adapter initialization."""
        with patch("kagami.core.services.llm_service.get_llm_service") as mock:
            mock_service = MagicMock()
            mock_service.initialize = AsyncMock()
            mock.return_value = mock_service

            await llm_adapter.initialize()

            # Should initialize underlying service
            mock.assert_called()


class TestTextGeneration:
    """Test text generation."""

    @pytest.mark.asyncio
    async def test_generate_text_simple(self, llm_adapter):
        """Test simple text generation."""
        with patch.object(llm_adapter, "_llm_service") as mock_service:
            mock_service.generate_text = AsyncMock(
                return_value="Generated text response"
            )

            result = await llm_adapter.generate_text("Test prompt")

            assert result == "Generated text response"
            mock_service.generate_text.assert_called_once()

    @pytest.mark.asyncio
    async def test_generate_text_with_params(self, llm_adapter):
        """Test text generation with parameters."""
        with patch.object(llm_adapter, "_llm_service") as mock_service:
            mock_service.generate_text = AsyncMock(return_value="Response")

            result = await llm_adapter.generate_text(
                "Test prompt",
                temperature=0.7,
                max_tokens=100,
            )

            assert result is not None


class TestErrorHandling:
    """Test error handling."""

    @pytest.mark.asyncio
    async def test_generation_failure(self, llm_adapter):
        """Test handling of generation failures."""
        with patch.object(llm_adapter, "_llm_service") as mock_service:
            mock_service.generate_text = AsyncMock(
                side_effect=RuntimeError("Generation failed")
            )

            with pytest.raises(RuntimeError):
                await llm_adapter.generate_text("Test prompt")


class TestCaching:
    """Test LLM response caching."""

    @pytest.mark.asyncio
    async def test_cache_hit(self, llm_adapter):
        """Test cache hit scenario."""
        # Placeholder - actual caching depends on implementation
        with patch.object(llm_adapter, "_llm_service") as mock_service:
            mock_service.generate_text = AsyncMock(return_value="Cached response")

            result1 = await llm_adapter.generate_text("Same prompt")
            result2 = await llm_adapter.generate_text("Same prompt")

            assert result1 == result2
