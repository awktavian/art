"""
Tests for CentralExperienceStore - the wiring that connects all subsystems.
"""

from __future__ import annotations
from typing import Any

import pytest

pytestmark = pytest.mark.tier_integration


import asyncio
import json

from kagami.core.coordination.experience_store import (
    CentralExperienceStore,
    get_experience_store,
)


@pytest.fixture
def temp_capsule(tmp_path: Any) -> None:
    """Create a temporary capsule.json."""
    capsule_path = tmp_path / "capsule.json"
    capsule_path.write_text(json.dumps({"recent_experiences": []}))
    return capsule_path


@pytest.fixture
def experience_store(temp_capsule: Any) -> Any:
    """Create experience store with temp capsule."""
    store = CentralExperienceStore()
    store._capsule_path = temp_capsule
    # Clear any loaded experiences
    store._recent_experiences = []
    return store


@pytest.mark.asyncio
async def test_record_experience_basic(experience_store: Any) -> Any:
    """Test basic experience recording."""
    context = {"action": "test", "app": "test_app"}
    action = {"action": "test_action"}
    outcome = {"status": "success", "duration_ms": 100}
    valence = 0.8

    await experience_store.record_experience(
        context=context, action=action, outcome=outcome, valence=valence
    )

    # Check it was stored
    assert len(experience_store._recent_experiences) == 1
    exp = experience_store._recent_experiences[0]
    assert exp["context"] == context
    assert exp["action"] == action
    assert exp["outcome"] == outcome
    assert exp["valence"] == valence
    assert "timestamp" in exp


@pytest.mark.asyncio
async def test_record_experience_updates_emotional_engine(experience_store: Any) -> None:
    """Test that recording updates the emotional engine."""
    from kagami.core.coordination.emotional_expression import get_emotional_engine

    engine = get_emotional_engine()
    initial_count = len(engine._recent_valences)

    context = {"action": "test"}
    action = {"action": "test"}
    outcome = {"status": "success", "duration_ms": 50}
    valence = 0.9

    await experience_store.record_experience(
        context=context, action=action, outcome=outcome, valence=valence
    )

    # Check emotional engine was updated
    assert len(engine._recent_valences) > initial_count
    assert engine._recent_valences[-1] == 0.9


@pytest.mark.asyncio
async def test_record_experience_high_valence_stored_in_learning(experience_store: Any) -> None:
    """Test that high-valence experiences go to learning instinct."""
    context = {"action": "important_task"}
    action = {"action": "critical"}
    outcome = {"status": "success", "duration_ms": 50}
    valence = 0.85  # High valence (> 0.7)

    await experience_store.record_experience(
        context=context, action=action, outcome=outcome, valence=valence
    )

    # This should trigger learning instinct storage (tested by no exception)
    # The actual learning instinct storage is tested elsewhere


@pytest.mark.asyncio
async def test_record_experience_max_recent_limit(experience_store: Any) -> None:
    """Test that recent experiences are limited to max_recent."""
    # Add more than max_recent experiences
    for i in range(25):  # max is 20
        await experience_store.record_experience(
            context={"action": f"test_{i}"},
            action={"action": "test"},
            outcome={"status": "success", "duration_ms": 100},
            valence=0.5,
        )

    # Should only keep 20
    assert len(experience_store._recent_experiences) == 20
    # Should keep the most recent ones
    assert experience_store._recent_experiences[-1]["context"]["action"] == "test_24"


@pytest.mark.asyncio
async def test_get_stats(experience_store: Any) -> None:
    """Test statistics calculation."""
    # Add mixed experiences
    experiences = [
        (0.8, "positive"),  # positive
        (0.5, "positive"),  # positive
        (-0.5, "negative"),  # negative
        (-0.8, "negative"),  # negative
        (0.1, "neutral"),  # neutral
    ]

    for valence, _ in experiences:
        await experience_store.record_experience(
            context={"action": "test"},
            action={"action": "test"},
            outcome={"status": "success", "duration_ms": 100},
            valence=valence,
        )

    stats = experience_store.get_stats()

    assert stats["count"] == 5
    assert stats["positive"] == 2  # > 0.3
    assert stats["negative"] == 2  # < -0.3
    assert stats["neutral"] == 1  # -0.3 to 0.3
    assert "avg_valence" in stats


@pytest.mark.asyncio
async def test_get_current_feeling(experience_store: Any) -> None:
    """Test that get_current_feeling uses emotional engine."""
    # Add some positive experiences
    for _ in range(5):
        await experience_store.record_experience(
            context={"action": "test"},
            action={"action": "test"},
            outcome={"status": "success", "duration_ms": 50},
            valence=0.8,
        )

    feeling = experience_store.get_current_feeling()

    # Should return a SystemFeeling object
    assert hasattr(feeling, "to_dict")
    feeling_dict = feeling.to_dict()
    assert "confidence" in feeling_dict
    assert "concern" in feeling_dict
    assert "tone" in feeling_dict
    assert "reflection" in feeling_dict


@pytest.mark.asyncio
async def test_capsule_persistence(temp_capsule: Any) -> None:
    """Test that experiences persist to capsule.json."""
    store = CentralExperienceStore()
    store._capsule_path = temp_capsule
    # Clear any loaded experiences
    store._recent_experiences = []

    # Add 10 experiences (triggers save)
    for i in range(10):
        await store.record_experience(
            context={"action": f"test_{i}"},
            action={"action": "test"},
            outcome={"status": "success", "duration_ms": 100},
            valence=0.5,
        )

    # Wait for async save to complete
    await asyncio.sleep(0.2)

    # Load capsule and check
    with open(temp_capsule) as f:
        data = json.load(f)

    assert "recent_experiences" in data
    assert len(data["recent_experiences"]) == 10


@pytest.mark.asyncio
async def test_load_from_capsule_on_startup(temp_capsule: Any) -> None:
    """Test that experiences load from capsule on startup."""
    # Populate capsule with experiences
    experiences = [
        {
            "context": {"action": "test"},
            "action": {"action": "test"},
            "outcome": {"status": "success", "duration_ms": 100},
            "valence": 0.8,
            "timestamp": 1234567890.0,
        }
    ]

    with open(temp_capsule, "w") as f:
        json.dump({"recent_experiences": experiences}, f)

    # Create new store (should load from capsule)
    store = CentralExperienceStore()
    store._capsule_path = temp_capsule
    store._load_from_capsule()

    assert len(store._recent_experiences) == 1
    assert store._recent_experiences[0]["context"]["action"] == "test"


def test_singleton_pattern():
    """Test that get_experience_store returns singleton."""
    store1 = get_experience_store()
    store2 = get_experience_store()

    assert store1 is store2


@pytest.mark.asyncio
async def test_experience_flows_to_replay_buffer(experience_store: Any) -> None:
    """Test that experiences flow to unified replay buffer."""
    from kagami.core.memory.unified_replay import get_unified_replay

    replay = get_unified_replay()
    initial_size = len(replay)

    await experience_store.record_experience(
        context={"action": "test"},
        action={"action": "test"},
        outcome={"status": "success", "duration_ms": 100},
        valence=0.7,
    )

    # Should have added to replay buffer
    assert len(replay) > initial_size


@pytest.mark.asyncio
async def test_consecutive_failures_tracked(experience_store: Any) -> None:
    """Test that consecutive failures are tracked in emotional engine."""
    from kagami.core.coordination.emotional_expression import get_emotional_engine

    engine = get_emotional_engine()
    engine._consecutive_failures = 0  # Reset

    # Add failures
    for _ in range(3):
        await experience_store.record_experience(
            context={"action": "test"},
            action={"action": "test"},
            outcome={"status": "error", "duration_ms": 100},
            valence=-0.8,
        )

    assert engine._consecutive_failures == 3

    # Add success (should reset)
    await experience_store.record_experience(
        context={"action": "test"},
        action={"action": "test"},
        outcome={"status": "success", "duration_ms": 50},
        valence=0.8,
    )

    assert engine._consecutive_failures == 0
