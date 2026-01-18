from __future__ import annotations

from typing import Any

import pytest

pytestmark = pytest.mark.tier_integration


from pydantic import BaseModel

from kagami.core.services.llm.generation_strategies import (
    _generate_standard,
    _generate_structured,
)
from kagami.core.services.llm.service import TaskType


class _DummyClient:
    def __init__(self) -> None:
        self.generate_calls = 0
        self.last_kwargs = None

    async def generate_text(self, prompt: str, max_tokens: int, temperature: float) -> str:
        self.generate_calls += 1
        self.last_kwargs = {  # type: ignore[assignment]
            "prompt": prompt,
            "max_tokens": max_tokens,
            "temperature": temperature,
        }
        return "stubbed-response"


class _DummyService:
    def __init__(self) -> None:
        self.client = _DummyClient()
        self.cache_requests = 0

    async def _get_or_create_client(
        self, provider: str, model_name: str, structured: bool
    ) -> _DummyClient:
        self.cache_requests += 1
        assert provider == "transformers"
        assert structured is False
        assert isinstance(model_name, str)
        return self.client


class _DummyFiltering:
    def __init__(self) -> None:
        self.sanitize_calls = 0
        self.validate_calls = 0

    def sanitize_output(self, text: str) -> str:
        self.sanitize_calls += 1
        return text

    def validate_text_output(
        self, text: str, app_name: str, task_type: TaskType, fmt: str | None
    ) -> str:
        self.validate_calls += 1
        return text


@pytest.mark.asyncio
async def test_generate_standard_prefers_cached_transformers_client(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Integration safeguard: `_generate_standard` must reuse the service cache."""

    # Force the production code path by clearing pytest's env hint.
    monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)
    monkeypatch.setenv("KAGAMI_TEST_ECHO_LLM", "0")

    # If the fallback factory is invoked, the test should fail.
    def _fail_create_transformers_client(*_args, **_kwargs) -> None:
        raise AssertionError(
            "create_transformers_client must not be called when cache is available"
        )

    monkeypatch.setattr(
        "kagami.core.services.llm.llm_providers.create_transformers_client",
        _fail_create_transformers_client,
    )

    monkeypatch.setattr(
        "kagami.core.services.llm.llm_filtering.LLMFiltering",
        _DummyFiltering,
    )

    service = _DummyService()

    result = await _generate_standard(
        service=service,
        prompt="hello world",
        app_name="test-app",
        task_type=TaskType.CONVERSATION,
        max_tokens=64,
        temperature=0.5,
        hints={},
    )

    assert result == "stubbed-response"
    assert service.cache_requests == 1
    assert service.client.generate_calls == 1


class _StructuredResponse(BaseModel):
    foo: str


class _DummyStructuredClient:
    def __init__(self) -> None:
        self.initialize_calls = 0
        self.generate_calls = 0
        self.last_kwargs = None

    async def initialize(self) -> None:
        self.initialize_calls += 1

    async def generate_structured(
        self,
        prompt: str,
        response_model: type[_StructuredResponse],
        max_tokens: int,
        temperature: float,
    ) -> _StructuredResponse:
        self.generate_calls += 1
        self.last_kwargs = {  # type: ignore[assignment]
            "prompt": prompt,
            "response_model": response_model,
            "max_tokens": max_tokens,
            "temperature": temperature,
        }
        return response_model(foo="bar")


@pytest.mark.asyncio
async def test_generate_structured_uses_structured_client(monkeypatch: pytest.MonkeyPatch) -> None:
    """Ensure `_generate_structured` wires through the structured client helper."""

    dummy_client = _DummyStructuredClient()

    monkeypatch.setattr(
        "kagami.core.services.llm.structured_client.get_structured_client",
        lambda: dummy_client,
        raising=False,
    )

    result = await _generate_structured(
        service=None,
        prompt="structured request",
        response_model=_StructuredResponse,
        max_tokens=42,
        temperature=0.1,
        hints={},
    )

    assert isinstance(result, _StructuredResponse)
    assert result.foo == "bar"
    assert dummy_client.initialize_calls == 1
    assert dummy_client.generate_calls == 1
    assert dummy_client.last_kwargs == {
        "prompt": "structured request",
        "response_model": _StructuredResponse,
        "max_tokens": 42,
        "temperature": 0.1,
    }
