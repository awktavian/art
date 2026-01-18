from __future__ import annotations

from typing import Any

import pytest

pytestmark = pytest.mark.tier_integration


import asyncio
from pathlib import Path


@pytest.mark.asyncio
async def test_character_growth_persistence(tmp_path: Any, monkeypatch: Any) -> None:
    # Redirect persistence to temp for isolation
    monkeypatch.setenv("KAGAMI_TEST_TEMP_STORAGE", str(tmp_path))

    from kagami.forge.persistence_manager import PersistenceManager
    from kagami.forge.schema import Character

    pm = PersistenceManager()

    # Create and save baseline character with personality
    ch = Character(name="Tester", concept="growth subject", personality={"traits": ["curious"]})
    ok = await pm.save_character(ch)
    assert ok is True

    # Apply growth feedback: add one trait, remove existing
    feedback = {"add_traits": ["resilient"], "remove_traits": ["curious"], "score": 0.9}
    ok2 = await pm.update_character_growth(ch.character_id, feedback)
    assert ok2 is True

    # Reload and verify version + trait changes + history
    ch2 = await pm.load_character(ch.character_id)
    assert ch2 is not None
    meta = ch2.metadata or {}
    assert int(meta.get("version", 0)) >= 1
    hist = meta.get("growth_history", [])
    assert isinstance(hist, list) and len(hist) >= 1
    # Traits updated
    pers = ch2.personality or {}
    traits = pers.get("traits", []) if isinstance(pers, dict) else getattr(pers, "traits", [])
    assert "resilient" in traits and "curious" not in traits

    # Index exists and includes summary
    index_path = (tmp_path if tmp_path else Path.home() / ".kagami" / "characters") / "index.json"
    if not index_path.exists():
        # If KAGAMI_TEST_TEMP_STORAGE was ignored due to env, build path from manager
        index_path = pm._index_path()

    assert index_path.exists()
    data = __import__("json").loads(index_path.read_text())
    assert ch2.character_id in data.get("characters", {})
    rec = data["characters"][ch2.character_id]
    assert isinstance(rec.get("personality_summary", ""), str)


@pytest.mark.asyncio
async def test_character_feedback_event_triggers_growth(tmp_path: Any, monkeypatch: Any) -> None:
    monkeypatch.setenv("KAGAMI_TEST_TEMP_STORAGE", str(tmp_path))

    from kagami.core.events.unified_e8_bus import get_unified_bus
    from kagami.forge.persistence_manager import PersistenceManager
    from kagami.forge.schema import Character

    pm = PersistenceManager()
    ch = Character(name="Eventy", concept="subject", personality={"traits": ["calm"]})
    await pm.save_character(ch)

    bus = get_unified_bus()
    if bus is None:
        pytest.skip("Unified E8 bus not initialized; skipping")
    # Publish feedback event
    await bus.publish(
        "character.feedback",
        {"character_id": ch.character_id, "feedback": {"add_traits": ["bold"]}},
    )

    # Give async handler a tick
    await asyncio.sleep(0.05)

    ch2 = await pm.load_character(ch.character_id)
    pers = ch2.personality if ch2 else {}
    traits = pers.get("traits", []) if isinstance(pers, dict) else getattr(pers, "traits", [])
    assert "bold" in traits
