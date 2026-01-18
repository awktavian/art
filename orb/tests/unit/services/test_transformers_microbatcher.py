from __future__ import annotations
from typing import Any

import asyncio

import pytest


@pytest.mark.asyncio
async def test_transformers_text_client_microbatcher_batches_requests(monkeypatch: Any) -> None:
    """Verify microbatcher groups concurrent requests into batched calls.

    We stub out actual model inference and only validate batching mechanics.
    """
    from kagami.core.services.llm.llm_providers import TransformersTextClient

    monkeypatch.setenv("KAGAMI_LLM_ENABLE_BATCHING", "1")
    monkeypatch.setenv("KAGAMI_LLM_MAX_BATCH_SIZE", "16")
    monkeypatch.setenv("KAGAMI_LLM_BATCH_MAX_WAIT_MS", "25")

    client = TransformersTextClient("dummy/model")

    # Avoid any real model loading.
    call_count = {"batch": 0}

    async def fake_unbatched(prompt: str, max_tokens: int, temperature: float) -> str:
        return f"unbatched:{prompt}"

    async def fake_batch(prompts: list[str], *, max_tokens: int, temperature: float) -> list[str]:
        call_count["batch"] += 1
        # Simulate a tiny bit of work so multiple tasks can coalesce.
        await asyncio.sleep(0.01)
        return [f"batched:{p}" for p in prompts]

    monkeypatch.setattr(client, "_generate_text_unbatched", fake_unbatched, raising=True)
    monkeypatch.setattr(client, "generate_text_batch", fake_batch, raising=True)

    # Fire a burst of concurrent requests with identical settings.
    tasks = [
        client.generate_text(prompt=f"p{i}", max_tokens=32, temperature=0.7) for i in range(10)
    ]
    outs = await asyncio.gather(*tasks)

    assert outs == [f"batched:p{i}" for i in range(10)]
    # With generous batch size and wait window, this should coalesce into one batch call.
    assert call_count["batch"] == 1
