from __future__ import annotations
from typing import Any

import pytest

pytestmark = pytest.mark.tier_integration


import asyncio

from kagami.core.routing.multi_model_router import MultiModelRouter, TaskType


def test_router_forces_keyword_mode_by_default_in_tests(monkeypatch: Any) -> None:
    """Ensure test env never triggers LLM classifier unless explicitly requested."""
    router = MultiModelRouter()
    called = {"llm": False}

    async def fake_llm_classifier(query: str, context: Any = None) -> Tuple[Any, ...]:
        called["llm"] = True
        return (TaskType.CODE_GENERATION, 0.9)

    # Ensure environment behaves like tests without explicit classifier override
    monkeypatch.setenv("KAGAMI_TEST_MODE", "1")
    monkeypatch.delenv("KAGAMI_ROUTER_CLASSIFIER_MODE", raising=False)
    monkeypatch.setattr(router, "classify_task_llm", fake_llm_classifier)

    router.route("write some code", task_type=None, prefer_local=True)
    assert called["llm"] is False


@pytest.mark.asyncio
async def test_classify_task_llm_respects_timeout(monkeypatch: Any) -> Any:
    router = MultiModelRouter()

    class SlowLLM:
        async def generate(self, *args: Any, **kwargs) -> Dict[str, Any]:
            await asyncio.sleep(0.05)
            return {"text": "general_reasoning|0.9"}

    monkeypatch.setattr("kagami.core.services.llm.service.get_llm_service", lambda: SlowLLM())
    monkeypatch.setenv("KAGAMI_ROUTER_CLASSIFIER_TIMEOUT_SECONDS", "0.01")

    task_type, confidence = await router.classify_task_llm("slow query")
    assert task_type == TaskType.GENERAL_REASONING
    assert confidence == 0.3
