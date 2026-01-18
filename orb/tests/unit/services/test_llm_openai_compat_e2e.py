from __future__ import annotations
from typing import Any

import pytest
from pydantic import BaseModel


class _Answer(BaseModel):
    answer: str


@pytest.mark.asyncio
async def test_openai_compatible_deepseek_e2e_text_and_structured(monkeypatch: Any) -> None:
    """End-to-end: service.generate -> OpenAI-compatible HTTP -> parse -> return.

    This exercises the "api" provider path used for DeepSeek-V3.2-Exp served behind
    vLLM/SGLang (OpenAI-compatible /v1/chat/completions).
    """
    monkeypatch.setenv("KAGAMI_LLM_PROVIDER", "api")
    monkeypatch.setenv("KAGAMI_LLM_API_BASE_URL", "http://testserver")
    monkeypatch.setenv("KAGAMI_LLM_API_MODEL", "deepseek-ai/DeepSeek-V3.2-Exp")
    monkeypatch.delenv("KAGAMI_TEST_ECHO_LLM", raising=False)

    # Stub httpx.AsyncClient used by OpenAICompatibleClient so this test has zero external deps.
    responses = [
        {"choices": [{"message": {"role": "assistant", "content": "pong"}}]},
        {"choices": [{"message": {"role": "assistant", "content": '{"answer": "pong"}'}}]},
    ]
    seen_urls: list[str] = []

    class _FakeHTTPXResponse:
        def __init__(self, payload: dict, status_code: int = 200) -> None:
            self._payload = payload
            self.status_code = status_code

        def raise_for_status(self) -> None:
            if int(self.status_code) >= 400:
                raise RuntimeError(f"HTTP {self.status_code}") from None

        def json(self) -> dict:
            return self._payload

    class _FakeAsyncClient:
        def __init__(self, *args, **kwargs) -> None:
            self._closed = False

        async def post(self, url: str, json: Any = None) -> Any:
            seen_urls.append(str(url))
            if not responses:
                raise AssertionError("No more fake responses configured") from None
            return _FakeHTTPXResponse(responses.pop(0), status_code=200)

        async def aclose(self) -> Any:
            self._closed = True

    import kagami.core.services.llm.openai_compatible_client as occ

    monkeypatch.setattr(occ.httpx, "AsyncClient", _FakeAsyncClient, raising=True)

    from kagami.core.services.llm.service import KagamiOSLLMService, TaskType

    svc = KagamiOSLLMService()

    text = await svc.generate(
        prompt="ping",
        app_name="test",
        task_type=TaskType.CONVERSATION,
        max_tokens=16,
        temperature=0.0,
    )
    assert text == "pong"

    structured = await svc.generate(
        prompt="Return JSON: {answer: string}",
        app_name="test",
        task_type=TaskType.EXTRACTION,
        max_tokens=64,
        temperature=0.0,
        structured_output=_Answer,
    )
    assert isinstance(structured, _Answer)
    assert structured.answer == "pong"
    assert seen_urls == [
        "http://testserver/v1/chat/completions",
        "http://testserver/v1/chat/completions",
    ]
