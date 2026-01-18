"""Tests for Frozen LLM Service.

Tests the frozen LLM service for goal generation and world model alignment.
"""

from __future__ import annotations
from typing import Any

import pytest

pytestmark = pytest.mark.tier_integration

import os
from unittest.mock import MagicMock, patch

import torch


@pytest.fixture
def mock_transformers():
    """Mock transformers library."""
    with (
        patch("transformers.AutoModelForCausalLM") as mock_model,
        patch("transformers.AutoTokenizer") as mock_tokenizer,
    ):
        # Mock tokenizer
        tokenizer = MagicMock()
        tokenizer.pad_token = None
        tokenizer.eos_token = "<eos>"
        tokenizer.pad_token_id = 0
        tokenizer.eos_token_id = 1
        tokenizer.vocab_size = 151936
        tokenizer.return_value = {
            "input_ids": torch.tensor([[1, 2, 3]]),
            "attention_mask": torch.tensor([[1, 1, 1]]),
        }

        def tokenizer_call(texts: Any, **kwargs) -> Any:
            # Create a mock object with .to() method
            result = MagicMock()

            if isinstance(texts, list):
                batch_size = len(texts)
                result_dict = {
                    "input_ids": torch.tensor([[1, 2, 3]] * batch_size),
                    "attention_mask": torch.tensor([[1, 1, 1]] * batch_size),
                }
            else:
                result_dict = {
                    "input_ids": torch.tensor([[1, 2, 3]]),
                    "attention_mask": torch.tensor([[1, 1, 1]]),
                }

            # Make result behave like dict but also have .to() method
            result.__getitem__ = lambda self, key: result_dict[key]
            result.keys = lambda: result_dict.keys()
            result.values = lambda: result_dict.values()
            result.items = lambda: result_dict.items()
            result.to = lambda device: result  # Return self for chaining

            return result

        tokenizer.side_effect = tokenizer_call
        tokenizer.decode = MagicMock(return_value="Generated text response")

        mock_tokenizer.from_pretrained.return_value = tokenizer

        # Mock model
        model = MagicMock()
        model.config.hidden_size = 3584
        model.parameters.return_value = [
            torch.nn.Parameter(torch.randn(100, 100)) for _ in range(10)
        ]

        # Mock generate method
        def generate(*args: Any, **kwargs) -> Any:
            return torch.tensor([[1, 2, 3, 4, 5]])

        model.generate = generate
        model.to.return_value = model
        model.eval.return_value = model

        mock_model.from_pretrained.return_value = model

        yield {
            "model_class": mock_model,
            "tokenizer_class": mock_tokenizer,
            "model": model,
            "tokenizer": tokenizer,
        }


@pytest.fixture(autouse=False)
def reset_singleton():
    """Reset frozen LLM singleton between tests."""
    from kagami.core.services.llm import frozen_llm_service

    # Save original values
    original_model = frozen_llm_service._frozen_llm_model
    original_tokenizer = frozen_llm_service._frozen_llm_tokenizer
    original_device = frozen_llm_service._frozen_llm_device

    # Reset to None BEFORE test
    frozen_llm_service._frozen_llm_model = None
    frozen_llm_service._frozen_llm_tokenizer = None
    frozen_llm_service._frozen_llm_device = "cpu"

    yield

    # Reset to None AFTER test (cleanup)
    frozen_llm_service._frozen_llm_model = None
    frozen_llm_service._frozen_llm_tokenizer = None
    frozen_llm_service._frozen_llm_device = "cpu"


class TestFrozenLLMService:
    """Test frozen LLM service."""

    def test_get_frozen_llm_device(self) -> None:
        """Test device detection."""
        from kagami.core.services.llm.frozen_llm_service import get_frozen_llm_device

        device = get_frozen_llm_device()
        assert device in ("cuda", "mps", "cpu")

    def test_get_frozen_llm_success(self, mock_transformers: Any, reset_singleton: Any) -> None:
        """Test successful LLM loading."""
        from kagami.core.services.llm.frozen_llm_service import get_frozen_llm

        model, tokenizer = get_frozen_llm()

        assert model is not None
        assert tokenizer is not None

        # Verify model was frozen
        for param in model.parameters():
            assert not param.requires_grad

    def test_get_frozen_llm_singleton(self, mock_transformers: Any, reset_singleton: Any) -> None:
        """Test singleton pattern."""
        from kagami.core.services.llm.frozen_llm_service import get_frozen_llm

        model1, tokenizer1 = get_frozen_llm()
        model2, tokenizer2 = get_frozen_llm()

        # Should return same instances
        assert model1 is model2
        assert tokenizer1 is tokenizer2

    def test_get_frozen_llm_failure(self, reset_singleton: Any) -> None:
        """Test LLM loading failure."""
        with patch("transformers.AutoTokenizer") as mock_tokenizer:
            mock_tokenizer.from_pretrained.side_effect = Exception("Load failed")

            from kagami.core.services.llm.frozen_llm_service import get_frozen_llm

            model, tokenizer = get_frozen_llm()

            assert model is None
            assert tokenizer is None

    @pytest.mark.asyncio
    async def test_generate_text_success(
        self, mock_transformers: Any, reset_singleton: Any
    ) -> None:
        """Test text generation."""
        from kagami.core.services.llm.frozen_llm_service import generate_text

        # Mock tokenizer decode to return prompt + response
        mock_transformers["tokenizer"].decode.return_value = "Test promptGenerated text response"

        response = await generate_text("Test prompt", max_tokens=100, temperature=0.8)

        assert response is not None
        assert isinstance(response, str)
        assert "Generated text response" in response

    @pytest.mark.asyncio
    async def test_generate_text_no_llm(self, reset_singleton: Any) -> None:
        """Test text generation without loaded LLM."""
        from kagami.core.services.llm import frozen_llm_service

        # Mock get_frozen_llm to return None, None
        with patch.object(frozen_llm_service, "get_frozen_llm", return_value=(None, None)):
            response = await frozen_llm_service.generate_text("Test prompt")
            assert response is None

    @pytest.mark.asyncio
    async def test_generate_text_parameters(
        self, mock_transformers: Any, reset_singleton: Any
    ) -> None:
        """Test text generation with custom parameters."""
        from kagami.core.services.llm.frozen_llm_service import generate_text

        mock_transformers["tokenizer"].decode.return_value = "Test promptCustom response"

        response = await generate_text(
            "Test prompt",
            max_tokens=50,
            temperature=0.5,
            top_p=0.95,
            do_sample=False,
        )

        assert response is not None
        assert "Custom response" in response

    @pytest.mark.asyncio
    async def test_batch_generate_text_success(
        self, mock_transformers: Any, reset_singleton: Any
    ) -> None:
        """Test batch text generation."""
        from kagami.core.services.llm.frozen_llm_service import batch_generate_text

        prompts = ["Prompt 1", "Prompt 2", "Prompt 3"]

        # Mock decode to return different responses
        decode_counter = [0]

        def mock_decode(tokens: Any, **kwargs) -> str:
            decode_counter[0] += 1
            return f"Prompt {decode_counter[0]}Generated response {decode_counter[0]}"

        mock_transformers["tokenizer"].decode = mock_decode

        # Mock model.generate to return 3 outputs
        def mock_generate(**kwargs) -> Any:
            return torch.tensor(
                [
                    [1, 2, 3, 4, 5],
                    [6, 7, 8, 9, 10],
                    [11, 12, 13, 14, 15],
                ]
            )

        mock_transformers["model"].generate = mock_generate

        responses = await batch_generate_text(prompts, max_tokens=100)

        assert len(responses) == 3
        assert all(r is not None for r in responses)
        assert all(isinstance(r, str) for r in responses)

    @pytest.mark.asyncio
    async def test_batch_generate_text_no_llm(self, reset_singleton: Any) -> Any:
        """Test batch generation without loaded LLM."""
        from kagami.core.services.llm import frozen_llm_service

        # Mock get_frozen_llm to return None, None
        with patch.object(frozen_llm_service, "get_frozen_llm", return_value=(None, None)):
            prompts = ["Prompt 1", "Prompt 2"]
            responses = await frozen_llm_service.batch_generate_text(prompts)

            assert len(responses) == 2
            assert all(r is None for r in responses)

    def test_is_frozen_llm_available(self, mock_transformers: Any, reset_singleton: Any) -> None:
        """Test availability check."""
        from kagami.core.services.llm.frozen_llm_service import (
            get_frozen_llm,
            is_frozen_llm_available,
        )

        # Initially not available
        assert not is_frozen_llm_available()

        # Load LLM
        get_frozen_llm()

        # Now available
        assert is_frozen_llm_available()

    def test_get_frozen_llm_stats_not_loaded(self, reset_singleton: Any) -> None:
        """Test stats when LLM not loaded."""
        from kagami.core.services.llm.frozen_llm_service import get_frozen_llm_stats

        stats = get_frozen_llm_stats()

        assert stats["loaded"] is False
        assert "device" in stats

    def test_get_frozen_llm_stats_loaded(
        self, mock_transformers: Any, reset_singleton: Any
    ) -> None:
        """Test stats when LLM loaded."""
        from kagami.core.services.llm.frozen_llm_service import (
            get_frozen_llm,
            get_frozen_llm_stats,
        )

        # Load LLM
        get_frozen_llm()

        stats = get_frozen_llm_stats()

        assert stats["loaded"] is True
        assert stats["hidden_size"] == 3584
        assert "vocab_size" in stats
        assert "num_parameters" in stats
        assert stats["trainable_parameters"] == 0  # All frozen

    def test_environment_model_selection(
        self, mock_transformers: Any, reset_singleton: Any
    ) -> None:
        """Test model selection from environment variables."""
        # Test KAGAMI_JOINT_LLM_MODEL
        with patch.dict(os.environ, {"KAGAMI_JOINT_LLM_MODEL": "test-model-1"}):
            from kagami.core.services.llm.frozen_llm_service import get_frozen_llm

            get_frozen_llm()

            mock_transformers["model_class"].from_pretrained.assert_called()
            call_args = mock_transformers["model_class"].from_pretrained.call_args[0]
            assert call_args[0] == "test-model-1"

    def test_frozen_parameters(self, mock_transformers: Any, reset_singleton: Any) -> None:
        """Test all parameters are frozen."""
        from kagami.core.services.llm.frozen_llm_service import get_frozen_llm

        model, _ = get_frozen_llm()

        assert model is not None

        # All parameters should have requires_grad=False
        for param in model.parameters():
            assert not param.requires_grad


class TestIntegrationWithMotivation:
    """Test integration with intrinsic motivation system."""

    @pytest.mark.asyncio
    async def test_curiosity_goal_generation(
        self, mock_transformers: Any, reset_singleton: Any
    ) -> None:
        """Test frozen LLM for curiosity goal generation."""
        from kagami.core.services.llm.frozen_llm_service import generate_text

        mock_transformers[
            "tokenizer"
        ].decode.return_value = (
            "Generate research questions: Research octonions and exceptional algebras"
        )

        prompt = "Generate research questions: "
        response = await generate_text(prompt, temperature=0.8)

        assert response is not None
        assert len(response) > 0

    @pytest.mark.asyncio
    async def test_competence_goal_generation(
        self, mock_transformers: Any, reset_singleton: Any
    ) -> None:
        """Test frozen LLM for competence goal generation."""
        from kagami.core.services.llm.frozen_llm_service import generate_text

        mock_transformers[
            "tokenizer"
        ].decode.return_value = "Improvement goals: Improve error recovery from 60% to 85%"

        prompt = "Improvement goals: "
        response = await generate_text(prompt, temperature=0.7)

        assert response is not None
        assert len(response) > 0


class TestIntegrationWithActionMapper:
    """Test integration with intelligent action mapper."""

    @pytest.mark.asyncio
    async def test_goal_to_action_mapping(
        self, mock_transformers: Any, reset_singleton: Any
    ) -> None:
        """Test frozen LLM for goal-to-action mapping."""
        from kagami.core.services.llm.frozen_llm_service import generate_text

        mock_transformers[
            "tokenizer"
        ].decode.return_value = (
            "Map goal: app: research\naction: research.web\nreasoning: Requires web search"
        )

        prompt = "Map goal: "
        response = await generate_text(prompt, temperature=0.3)

        assert response is not None
        assert "research" in response.lower()


class TestErrorHandling:
    """Test error handling and edge cases."""

    @pytest.mark.asyncio
    async def test_generation_exception(self, mock_transformers: Any, reset_singleton: Any) -> None:
        """Test generation with exception."""
        from kagami.core.services.llm.frozen_llm_service import (
            generate_text,
            get_frozen_llm,
        )

        # Load LLM first
        get_frozen_llm()

        # Make generate raise exception
        mock_transformers["model"].generate = MagicMock(side_effect=Exception("Generation failed"))

        response = await generate_text("Test prompt")

        assert response is None

    @pytest.mark.asyncio
    async def test_batch_generation_exception(
        self, mock_transformers: Any, reset_singleton: Any
    ) -> None:
        """Test batch generation with exception."""
        from kagami.core.services.llm.frozen_llm_service import (
            batch_generate_text,
            get_frozen_llm,
        )

        # Load LLM first
        get_frozen_llm()

        # Make generate raise exception
        mock_transformers["model"].generate = MagicMock(
            side_effect=Exception("Batch generation failed")
        )

        prompts = ["Prompt 1", "Prompt 2"]
        responses = await batch_generate_text(prompts)

        assert len(responses) == 2
        assert all(r is None for r in responses)

    def test_stats_with_invalid_model(self, reset_singleton: Any) -> None:
        """Test stats with invalid model state."""
        from kagami.core.services.llm import frozen_llm_service

        # Ensure model is NOT loaded (the function checks this first)
        frozen_llm_service._frozen_llm_model = None
        frozen_llm_service._frozen_llm_tokenizer = None

        stats = frozen_llm_service.get_frozen_llm_stats()

        # Should return unloaded stats
        assert isinstance(stats, dict)
        assert stats["loaded"] is False
