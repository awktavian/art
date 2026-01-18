"""Test frozen LLM integration with LLM service.

Verifies that the LLM service properly falls back to frozen LLM
when progressive loading is unavailable.
"""

from __future__ import annotations

import pytest
pytestmark = pytest.mark.tier_unit



from kagami.core.services.llm import (
    FrozenLLMService,
    get_frozen_llm_service,
    get_llm_service,
    is_frozen_llm_available,
)


@pytest.mark.asyncio
async def test_frozen_llm_service_singleton():
    """Test that get_frozen_llm_service returns singleton."""
    service1 = get_frozen_llm_service()
    service2 = get_frozen_llm_service()

    assert service1 is service2
    assert isinstance(service1, FrozenLLMService)


@pytest.mark.asyncio
async def test_frozen_llm_service_generate():
    """Test that FrozenLLMService.generate works."""
    service = get_frozen_llm_service()

    # Skip test if frozen LLM not available (transformers not installed)
    if not is_frozen_llm_available():
        pytest.skip("Frozen LLM not available (transformers not installed)")

    prompt = "What is 2+2?"
    response = await service.generate(prompt, max_tokens=10, temperature=0.1)

    assert isinstance(response, str)
    # Should return something (not empty)
    assert len(response) > 0


@pytest.mark.asyncio
async def test_llm_service_generate_simple():
    """Test that KagamiOSLLMService.generate_simple works."""
    service = get_llm_service()

    # Skip test if frozen LLM not available
    if not is_frozen_llm_available():
        pytest.skip("Frozen LLM not available")

    prompt = "Count to three:"
    response = await service.generate_simple(prompt, max_tokens=20, temperature=0.1)

    assert isinstance(response, str)
    assert len(response) > 0


@pytest.mark.asyncio
async def test_get_model_for_task_fallback():
    """Test that get_model_for_task falls back to frozen LLM."""
    service = get_llm_service()

    # Skip test if frozen LLM not available
    if not is_frozen_llm_available():
        pytest.skip("Frozen LLM not available")

    # Get model (should fallback to frozen LLM wrapper if progressive loading unavailable)
    model = await service.get_model_for_task("standard")

    # Should return something (either progressive loader model or frozen wrapper)
    assert model is not None

    # If it's a frozen wrapper, verify it has generate method
    if hasattr(model, "generate"):
        response = await model.generate("Test prompt", max_tokens=10)
        assert isinstance(response, str)


@pytest.mark.asyncio
async def test_frozen_llm_wrapper_interface():
    """Test that frozen LLM wrapper has correct interface."""
    service = get_llm_service()

    # Create wrapper directly
    wrapper = service._create_frozen_llm_wrapper()

    # Skip test if frozen LLM not available
    if not is_frozen_llm_available():
        pytest.skip("Frozen LLM not available")

    # Verify interface
    assert hasattr(wrapper, "generate")

    # Test generation
    response = await wrapper.generate("Test:", max_tokens=5, temperature=0.1)
    assert isinstance(response, str)


@pytest.mark.asyncio
async def test_llm_service_init_without_crash():
    """Test that LLM service initializes without crashing."""
    service = get_llm_service()

    # Should initialize without error
    await service.initialize()

    # Should be initialized
    assert service.is_initialized


@pytest.mark.asyncio
async def test_generate_simple_with_empty_response():
    """Test that generate_simple handles empty responses gracefully."""
    service = get_llm_service()

    # Even with invalid prompt, should return string (not None)
    response = await service.generate_simple("", max_tokens=1, temperature=0.0)

    assert isinstance(response, str)
    # Empty response should return empty string (not None)
    assert response == ""


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
