"""Test persistence of Character concept field."""

from __future__ import annotations

from typing import Any

import pytest

pytestmark = pytest.mark.tier_integration


import shutil
import tempfile

from kagami.forge.persistence_manager import PersistenceManager
from kagami.forge.schema import Character


@pytest.fixture
def temp_storage(monkeypatch: Any) -> Any:
    """Create temporary storage for testing and isolate via env."""
    temp_dir = tempfile.mkdtemp()
    # Point PersistenceManager to this directory to avoid cross-test pollution
    monkeypatch.setenv("KAGAMI_TEST_TEMP_STORAGE", temp_dir)
    yield temp_dir
    shutil.rmtree(temp_dir)


@pytest.mark.asyncio
async def test_character_concept_persistence(temp_storage: Any) -> None:
    """Test saving and loading character with concept field."""
    # Setup persistence manager (uses in-memory storage)
    pm = PersistenceManager()

    # Create character with concept
    character = Character(
        name="Test Hero",
        concept="A brave warrior with a mysterious past who fights for justice",
    )

    # Save character
    success = await pm.save_character(character)
    assert success is True
    char_id = character.character_id

    # Load character
    loaded_char = await pm.load_character(char_id)
    assert loaded_char is not None
    assert loaded_char.name == "Test Hero"
    assert loaded_char.concept == "A brave warrior with a mysterious past who fights for justice"


@pytest.mark.asyncio
async def test_character_concept_in_list(temp_storage: Any) -> None:
    """Test that concept appears in character list."""
    # Setup persistence manager (uses in-memory storage)
    pm = PersistenceManager()

    # Create and save character with concept
    character = Character(
        name="Dragon Knight", concept="An ancient dragon transformed into human form"
    )
    await pm.save_character(character)

    # List characters
    char_list = await pm.list_characters()
    assert len(char_list) == 1
    assert char_list[0].name == "Dragon Knight"
    assert char_list[0].concept == "An ancient dragon transformed into human form"


def test_character_to_from_dict() -> None:
    """Test Character to_dict and from_dict methods."""
    # Create character with concept
    original = Character(name="Magic User", concept="A powerful wizard seeking forbidden knowledge")

    # Convert to dict
    char_dict = original.to_dict()
    assert "concept" in char_dict
    assert char_dict["concept"] == "A powerful wizard seeking forbidden knowledge"

    # Convert back from dict
    restored = Character.from_dict(char_dict)
    assert restored.name == "Magic User"
    assert restored.concept == "A powerful wizard seeking forbidden knowledge"
    assert restored.character_id == original.character_id
