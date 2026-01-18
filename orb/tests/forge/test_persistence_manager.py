"""Comprehensive tests for forge persistence_manager module.

Tests PersistenceManager class and character persistence.
"""

from __future__ import annotations

from typing import Any

import pytest

pytestmark = pytest.mark.tier_integration


import json
import tempfile
from pathlib import Path

from kagami.forge.persistence_manager import PersistenceManager
from kagami.forge.schema import Character


@pytest.fixture
def temp_storage(monkeypatch: Any) -> Any:
    """Create temporary storage for testing."""
    with tempfile.TemporaryDirectory() as temp_dir:
        monkeypatch.setenv("KAGAMI_TEST_TEMP_STORAGE", temp_dir)
        yield temp_dir


class TestPersistenceManager:
    """Test PersistenceManager class."""

    def test_creation(self: Any, temp_storage: Any) -> None:
        """Test creating a persistence manager."""
        pm = PersistenceManager()
        assert pm._storage_dir.exists()

    def test_creation_with_custom_dir(self: Any, tmp_path: Any) -> None:
        """Test creating with custom storage directory."""
        pm = PersistenceManager(storage_dir=tmp_path / "custom")
        assert pm._storage_dir == tmp_path / "custom"
        assert pm._storage_dir.exists()


class TestSaveCharacter:
    """Test character saving functionality."""

    @pytest.mark.asyncio
    async def test_save_character_success(self: Any, temp_storage: Any) -> None:
        """Test successfully saving a character."""
        pm = PersistenceManager()
        char = Character(name="Test Hero", concept="A brave warrior")

        result = await pm.save_character(char)

        assert result is True
        # Verify file was created
        path = pm._path_for(char.character_id)
        assert path.exists()

    @pytest.mark.asyncio
    async def test_save_character_invalid_type(self: Any, temp_storage: Any) -> None:
        """Test saving non-Character raises error."""
        pm = PersistenceManager()

        with pytest.raises(ValueError, match="Expected Character object"):
            await pm.save_character({"name": "Invalid"})  # type: ignore[arg-type]

    @pytest.mark.asyncio
    async def test_save_character_no_id(self: Any, temp_storage: Any) -> None:
        """Test saving character without ID raises error."""
        pm = PersistenceManager()
        char = Character(name="Test")
        char.character_id = ""

        with pytest.raises(ValueError, match="must have a character_id"):
            await pm.save_character(char)

    @pytest.mark.asyncio
    async def test_save_character_no_name(self: Any, temp_storage: Any) -> None:
        """Test saving character without name raises error."""
        pm = PersistenceManager()
        char = Character()
        char.name = ""

        with pytest.raises(ValueError, match="non-empty name"):
            await pm.save_character(char)

    @pytest.mark.asyncio
    async def test_save_character_updates_index(self: Any, temp_storage: Any) -> None:
        """Test saving character updates the index."""
        pm = PersistenceManager()
        char = Character(name="Indexed Hero", concept="Testing index")

        await pm.save_character(char)

        index_path = pm._index_path()
        assert index_path.exists()

        index = json.loads(index_path.read_text())
        assert char.character_id in index.get("characters", {})


class TestLoadCharacter:
    """Test character loading functionality."""

    @pytest.mark.asyncio
    async def test_load_character_success(self: Any, temp_storage: Any) -> None:
        """Test successfully loading a character."""
        pm = PersistenceManager()
        char = Character(name="Load Test", concept="Testing load")
        await pm.save_character(char)

        loaded = await pm.load_character(char.character_id)

        assert loaded is not None
        assert loaded.name == "Load Test"
        assert loaded.concept == "Testing load"

    @pytest.mark.asyncio
    async def test_load_character_not_found(self: Any, temp_storage: Any) -> None:
        """Test loading non-existent character returns None."""
        pm = PersistenceManager()

        loaded = await pm.load_character("nonexistent-id")

        assert loaded is None

    @pytest.mark.asyncio
    async def test_load_character_caches(self: Any, temp_storage: Any) -> None:
        """Test loaded character is cached."""
        pm = PersistenceManager()
        char = Character(name="Cache Test", concept="Testing cache")
        await pm.save_character(char)

        # Clear cache
        pm._characters.clear()

        loaded = await pm.load_character(char.character_id)

        assert char.character_id in pm._characters


class TestListCharacters:
    """Test character listing functionality."""

    @pytest.mark.asyncio
    async def test_list_characters_empty(self: Any, temp_storage: Any) -> None:
        """Test listing when no characters exist."""
        pm = PersistenceManager()

        result = await pm.list_characters()

        assert result == []

    @pytest.mark.asyncio
    async def test_list_characters_with_data(self: Any, temp_storage: Any) -> None:
        """Test listing characters returns all."""
        pm = PersistenceManager()
        for i in range(3):
            char = Character(name=f"Hero {i}", concept=f"Concept {i}")
            await pm.save_character(char)

        result = await pm.list_characters()

        assert len(result) == 3

    @pytest.mark.asyncio
    async def test_list_characters_pagination(self: Any, temp_storage: Any) -> None:
        """Test listing with pagination."""
        pm = PersistenceManager()
        for i in range(5):
            char = Character(name=f"Hero {i}", concept=f"Concept {i}")
            await pm.save_character(char)

        result = await pm.list_characters(limit=2, offset=1)

        assert len(result) == 2


class TestDeleteCharacter:
    """Test character deletion functionality."""

    @pytest.mark.asyncio
    async def test_delete_character_success(self: Any, temp_storage: Any) -> None:
        """Test successfully deleting a character."""
        pm = PersistenceManager()
        char = Character(name="Delete Test", concept="To be deleted")
        await pm.save_character(char)

        result = await pm.delete_character(char.character_id)

        assert result is True
        path = pm._path_for(char.character_id)
        assert not path.exists()

    @pytest.mark.asyncio
    async def test_delete_character_removes_from_cache(self: Any, temp_storage: Any) -> None:
        """Test deletion removes from cache."""
        pm = PersistenceManager()
        char = Character(name="Cache Delete", concept="Testing")
        await pm.save_character(char)

        await pm.delete_character(char.character_id)

        assert char.character_id not in pm._characters

    @pytest.mark.asyncio
    async def test_delete_nonexistent_character(self: Any, temp_storage: Any) -> None:
        """Test deleting non-existent character succeeds."""
        pm = PersistenceManager()

        result = await pm.delete_character("nonexistent-id")

        assert result is True


class TestSearchCharacters:
    """Test character search functionality."""

    @pytest.mark.asyncio
    async def test_search_by_name(self: Any, temp_storage: Any) -> None:
        """Test searching by name."""
        pm = PersistenceManager()
        char1 = Character(name="Dragon Knight", concept="A warrior")
        char2 = Character(name="Fire Mage", concept="A spellcaster")
        await pm.save_character(char1)
        await pm.save_character(char2)

        results = await pm.search_characters("Dragon")

        assert len(results) == 1
        assert results[0].name == "Dragon Knight"

    @pytest.mark.asyncio
    async def test_search_by_concept(self: Any, temp_storage: Any) -> None:
        """Test searching by concept."""
        pm = PersistenceManager()
        char1 = Character(name="Hero", concept="fights dragons")
        char2 = Character(name="Mage", concept="casts spells")
        await pm.save_character(char1)
        await pm.save_character(char2)

        results = await pm.search_characters("dragons")

        assert len(results) == 1
        assert results[0].name == "Hero"

    @pytest.mark.asyncio
    async def test_search_no_results(self: Any, temp_storage: Any) -> None:
        """Test search with no matches."""
        pm = PersistenceManager()
        char = Character(name="Hero", concept="A warrior")
        await pm.save_character(char)

        results = await pm.search_characters("nonexistent")

        assert len(results) == 0


class TestUpdateCharacterGrowth:
    """Test character growth update functionality."""

    @pytest.mark.asyncio
    async def test_update_growth_adds_trait(self: Any, temp_storage: Any) -> None:
        """Test adding traits via growth update."""
        pm = PersistenceManager()
        char = Character(name="Growing Hero", concept="Testing", personality={"traits": ["brave"]})
        await pm.save_character(char)

        feedback = {"add_traits": ["wise"], "score": 0.9}
        result = await pm.update_character_growth(char.character_id, feedback)

        assert result is True

        loaded = await pm.load_character(char.character_id)
        traits = loaded.personality.get("traits", [])  # type: ignore[union-attr]
        assert "wise" in traits
        assert "brave" in traits

    @pytest.mark.asyncio
    async def test_update_growth_removes_trait(self: Any, temp_storage: Any) -> None:
        """Test removing traits via growth update."""
        pm = PersistenceManager()
        char = Character(
            name="Changing Hero",
            concept="Testing",
            personality={"traits": ["reckless", "brave"]},
        )
        await pm.save_character(char)

        feedback = {"remove_traits": ["reckless"]}
        result = await pm.update_character_growth(char.character_id, feedback)

        assert result is True

        loaded = await pm.load_character(char.character_id)
        traits = loaded.personality.get("traits", [])  # type: ignore[union-attr]
        assert "reckless" not in traits
        assert "brave" in traits

    @pytest.mark.asyncio
    async def test_update_growth_increments_version(self: Any, temp_storage: Any) -> None:
        """Test version increments on growth update."""
        pm = PersistenceManager()
        char = Character(name="Versioned", concept="Testing")
        await pm.save_character(char)

        await pm.update_character_growth(char.character_id, {"score": 0.8})
        await pm.update_character_growth(char.character_id, {"score": 0.9})

        loaded = await pm.load_character(char.character_id)
        assert int(loaded.metadata.get("version", 0)) >= 2  # type: ignore[union-attr]

    @pytest.mark.asyncio
    async def test_update_growth_nonexistent_fails(self: Any, temp_storage: Any) -> None:
        """Test updating non-existent character fails."""
        pm = PersistenceManager()

        result = await pm.update_character_growth("nonexistent", {"score": 0.5})

        assert result is False


class TestSaveWorldExport:
    """Test world export saving functionality."""

    @pytest.mark.asyncio
    async def test_save_world_export(self: Any, temp_storage: Any) -> None:
        """Test saving world export record."""
        pm = PersistenceManager()

        result = await pm.save_world_export(
            session_id="session-001",
            export_path="/exports/world.usd",
            package_path="/packages/world.zip",
            manifest={"assets": 5},
        )

        assert result is True

        export_dir = pm._storage_dir / "world_exports"
        export_file = export_dir / "session-001.json"
        assert export_file.exists()


class TestIndexHelpers:
    """Test index helper methods."""

    def test_index_path(self: Any, temp_storage: Any) -> None:
        """Test index path generation."""
        pm = PersistenceManager()
        path = pm._index_path()

        assert path.name == "index.json"

    def test_load_index_empty(self: Any, temp_storage: Any) -> None:
        """Test loading non-existent index."""
        pm = PersistenceManager()
        index = pm._load_index()

        assert index == {"characters": {}}

    def test_summarize_personality_dict(self: Any, temp_storage: Any) -> None:
        """Test personality summary from dict."""
        pm = PersistenceManager()
        char = Character(
            name="Test",
            concept="Testing",
            personality={"traits": ["brave", "wise", "strong"]},
        )

        summary = pm._summarize_personality(char)

        assert "brave" in summary
        assert "wise" in summary
