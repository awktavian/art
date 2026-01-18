from __future__ import annotations
from typing import Any

import pytest

pytestmark = pytest.mark.tier_integration
from kagami.core.services.llm.service import KagamiOSLLMService, TaskType


@pytest.mark.asyncio
async def test_text_validation_non_empty(monkeypatch: Any) -> None:
    svc = KagamiOSLLMService()

    class _Echo:
        def __init__(self):
            self.config = type("Cfg", (), {"provider": "test", "model_name": "echo"})()
            self.is_test_client = True

        async def reason_async(self, prompt_or_obj: Any) -> str:
            return "  "

    async def _select_model(_: Any, __: Any, ___: Any, ____: Any) -> Any:
        return _Echo()

    monkeypatch.setattr(svc, "_select_model", _select_model)
    await svc.initialize()
    with pytest.raises(ValueError):
        await svc.generate(
            prompt="hello",
            app_name="System",
            task_type=TaskType.SUMMARY,
            routing_hints={"format": "text"},
        )


@pytest.mark.asyncio
async def test_json_validation_invalid(monkeypatch: Any) -> Any:
    svc = KagamiOSLLMService()

    class _Echo:
        def __init__(self):
            self.config = type("Cfg", (), {"provider": "test", "model_name": "echo"})()
            self.is_test_client = True

        async def reason_async(self, prompt_or_obj: Any) -> str:
            return "not json"

    async def _select_model(_: Any, __: Any, ___: Any, ____: Any) -> Any:
        return _Echo()

    monkeypatch.setattr(svc, "_select_model", _select_model)
    await svc.initialize()
    with pytest.raises(ValueError):
        await svc.generate(
            prompt="return json",
            app_name="System",
            task_type=TaskType.SUMMARY,
            routing_hints={"format": "json"},
        )


@pytest.mark.asyncio
async def test_json_validation_valid(monkeypatch: Any) -> Any:
    svc = KagamiOSLLMService()

    class _Echo:
        def __init__(self):
            self.config = type("Cfg", (), {"provider": "test", "model_name": "echo"})()
            self.is_test_client = True

        async def reason_async(self, prompt_or_obj: Any) -> Any:
            return '{"a":1}'

    async def _select_model(_: Any, __: Any, ___: Any, ____: Any) -> Any:
        return _Echo()

    monkeypatch.setattr(svc, "_select_model", _select_model)
    await svc.initialize()
    out = await svc.generate(
        prompt="return json",
        app_name="System",
        task_type=TaskType.SUMMARY,
        routing_hints={"format": "json"},
    )
    assert isinstance(out, str)
    assert out.strip().startswith("{")
