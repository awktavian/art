"""Mock LLM service for testing without loading heavy models.

Provides a lightweight mock implementation of the LLM service that
returns predictable responses for tests that don't need actual
model inference quality.
"""

from typing import Any
from unittest.mock import MagicMock

import pytest


class MockLLMResponse:
    """Mock LLM response object."""

    def __init__(self, text: str = "Mock LLM response", **kwargs) -> None:
        self.text = text
        self.content = text
        self.choices = [MagicMock(message=MagicMock(content=text))]
        self.model = kwargs.get("model", "mock-model")
        self.usage = MagicMock(prompt_tokens=10, completion_tokens=20, total_tokens=30)

        # Support Pydantic model extraction
        for key, value in kwargs.items():
            setattr(self, key, value)

    def model_dump(self):
        """Return dict representation for Pydantic compatibility."""
        return {"text": self.text, "content": self.content}


class MockLLMService:
    """Mock LLM service that returns predictable responses."""

    def __init__(self, default_response: str = "Mock response"):
        self.default_response = default_response
        self.call_count = 0
        self.calls = []

    async def generate(
        self,
        prompt: str = "",
        system_prompt: str = "",
        max_tokens: int = 100,
        temperature: float = 0.7,
        **kwargs: Any,
    ) -> MockLLMResponse:
        """Generate a mock response."""
        self.call_count += 1
        self.calls.append(
            {
                "prompt": prompt,
                "system_prompt": system_prompt,
                "max_tokens": max_tokens,
                "temperature": temperature,
                "kwargs": kwargs,
            }
        )

        # Return context-aware responses for common test patterns
        if "error" in prompt.lower():
            return MockLLMResponse("Error: Test error response")
        elif "json" in prompt.lower() or kwargs.get("format") == "json":
            return MockLLMResponse('{"result": "success", "value": 42}')
        elif "code" in prompt.lower():
            return MockLLMResponse("def test(): return True")
        else:
            return MockLLMResponse(self.default_response)

    async def generate_structured(self, prompt: str = "", schema: Any = None, **kwargs) -> Any:
        """Generate structured output."""
        self.call_count += 1

        # Return schema-compatible mock
        if schema:
            # Try to instantiate the schema with mock data
            try:
                if hasattr(schema, "model_validate"):
                    # Pydantic v2
                    return schema.model_validate({"value": "mock"})
                elif hasattr(schema, "parse_obj"):
                    # Pydantic v1
                    return schema.parse_obj({"value": "mock"})
            except Exception:
                pass

        return MockLLMResponse('{"value": "mock"}')

    def reset(self):
        """Reset call tracking."""
        self.call_count = 0
        self.calls = []


@pytest.fixture
def mock_llm_service():
    """Provide a mock LLM service for tests."""
    return MockLLMService()


@pytest.fixture
def mock_llm_response():
    """Provide a mock LLM response factory."""

    def _create_response(text: str = "Mock response", **kwargs) -> Any:
        return MockLLMResponse(text, **kwargs)

    return _create_response


@pytest.fixture
def patch_llm_service(monkeypatch: Any, mock_llm_service: Any) -> Any:
    """Patch the LLM service to use mock implementation."""
    # Patch the main LLM service
    try:
        from kagami.core.services.llm import service

        monkeypatch.setattr(service, "KagamiOSLLMService", lambda: mock_llm_service)
    except ImportError:
        pass

    # Patch structured generation
    try:
        from kagami.core.services.llm import structured as llm_structured

        async def mock_generate_structured(*args: Any, **kwargs) -> None:
            return await mock_llm_service.generate_structured(*args, **kwargs)

        monkeypatch.setattr(
            llm_structured, "generate_structured_enhanced", mock_generate_structured
        )
    except ImportError:
        pass

    return mock_llm_service


@pytest.fixture(scope="session")
def ensure_test_models_available():
    """Ensure lightweight test models are available.

    This fixture runs once per test session to verify that
    tiny-gpt2 is available for tests.
    """
    import os

    # Models are configured via test_env.py
    # This fixture just validates the configuration
    assert os.environ.get("KAGAMI_TEST_MODE") == "1", "Test mode not enabled"
    assert "tiny-gpt2" in os.environ.get(
        "KAGAMI_TRANSFORMERS_MODEL_DEFAULT", ""
    ), "Lightweight test model not configured"

    yield

    # Cleanup after all tests
    # (Nothing to clean up for this fixture)


@pytest.fixture
def real_llm_service():
    """Provide the real LLM service for tests that need it.

    Use this fixture with @pytest.mark.real_model for tests that
    validate actual LLM output quality.
    """
    from kagami.core.services.llm.service import KagamiOSLLMService

    return KagamiOSLLMService()
