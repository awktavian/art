from __future__ import annotations
from typing import Any

import pytest

pytestmark = pytest.mark.tier_unit


@pytest.mark.asyncio
@pytest.mark.timeout(10)  # 10 second timeout for network-dependent test
async def test_research_flow_with_mocked_network(monkeypatch: Any) -> None:
    from kagami.tools.web import search as ws_mod

    async def fake_search_web(_query: str, _top_k: int = 5):
        return [
            ws_mod.SearchHit(title="T1", url="https://example.com/1", snippet="s1", source="local"),
            ws_mod.SearchHit(title="T2", url="https://example.com/2", snippet="s2", source="local"),
        ]

    monkeypatch.setattr(ws_mod, "search_web", fake_search_web)

    results = await ws_mod.web_search("octonions", max_results=2, timeout=5.0)
    assert isinstance(results, list)
    assert len(results) == 2
    assert results[0]["title"] == "T1"
    assert results[0]["url"].startswith("https://")
    assert "snippet" in results[0]
