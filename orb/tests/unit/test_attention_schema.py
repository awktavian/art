from __future__ import annotations

import pytest

pytestmark = pytest.mark.tier_unit


import asyncio

from kagami.core.workspace.attention_schema import get_attention_schema


@pytest.mark.unit
def test_attention_recommendation_basic() -> None:
    schema = get_attention_schema()
    # Seed two candidates via events
    schema.observe_event("intent.execute", {"agent": "sage"})
    schema.observe_event("ui.click", {"user_id": "u1"})

    rec = schema.recommend_focus()
    assert isinstance(rec, dict)
    assert rec.get("decision") in {"stay", "switch", "avoid_switch"}


@pytest.mark.unit
@pytest.mark.asyncio
async def test_set_focus_tracks_dwell_and_confidence() -> None:
    schema = get_attention_schema()
    await schema.set_focus("phase:perceive", 0.8, owner_type="self", reason="test")
    await asyncio.sleep(0.01)
    await schema.set_focus("phase:simulate", 0.9, owner_type="self", reason="test")
    snap = schema.get_snapshot(top_k=3)
    assert "current_focus" in snap
    assert isinstance(snap.get("candidates"), list)
