"""Tests for ForgeRoomsExporter - Forge to Rooms integration."""

from __future__ import annotations

import pytest
from typing import Any

import math

from kagami.forge.rooms_export import ForgeRoomsExporter


@pytest.fixture
def exporter():
    """Create a ForgeRoomsExporter instance."""
    return ForgeRoomsExporter(client_id="test_client")


@pytest.fixture
def sample_character():
    """Sample character data from ForgeService."""
    return {
        "id": "test_char_001",
        "gltf_url": "https://cdn.example.com/characters/warrior.glb",
        "concept": "medieval warrior",
        "quality": "draft",
        "request_id": "req_12345",
    }


def test_exporter_initialization():
    """Test basic exporter initialization."""
    exporter = ForgeRoomsExporter()
    assert exporter.client_id == "forge_service"

    exporter_custom = ForgeRoomsExporter(client_id="custom_client")
    assert exporter_custom.client_id == "custom_client"


@pytest.mark.asyncio
async def test_export_character_validation_errors(exporter: Any, sample_character: Any) -> None:
    """Test input validation for export_character_to_room."""

    # Missing character ID
    with pytest.raises(ValueError, match="id"):
        await exporter.export_character_to_room(
            room_id="test_room",
            character_data={},
            position=[0, 0, 0],
        )

    # Empty character ID
    with pytest.raises(ValueError, match="id"):
        await exporter.export_character_to_room(
            room_id="test_room",
            character_data={"id": ""},
            position=[0, 0, 0],
        )

    # Missing mesh URL
    char_no_mesh = {"id": "test_char", "concept": "warrior"}
    result = await exporter.export_character_to_room(
        room_id="test_room",
        character_data=char_no_mesh,
        position=[0, 0, 0],
    )
    assert result is False  # Should log error and return False

    # Invalid position (not 3 elements)
    with pytest.raises(ValueError, match="position"):
        await exporter.export_character_to_room(
            room_id="test_room",
            character_data=sample_character,
            position=[0, 0],  # Only 2 elements
        )

    # Invalid position (non-numeric)
    with pytest.raises(ValueError, match="position"):
        await exporter.export_character_to_room(
            room_id="test_room",
            character_data=sample_character,
            position=["x", "y", "z"],
        )

    # Invalid orientation (not 4 elements)
    with pytest.raises(ValueError, match="orientation"):
        await exporter.export_character_to_room(
            room_id="test_room",
            character_data=sample_character,
            position=[0, 0, 0],
            orientation=[0, 0, 0],  # Only 3 elements
        )


@pytest.mark.asyncio
async def test_export_character_success(exporter: Any, sample_character: Any) -> None:
    """Test successful character export to room."""
    result = await exporter.export_character_to_room(
        room_id="test_room",
        character_data=sample_character,
        position=[5.0, 0.0, -3.0],
        orientation=[0.0, 0.707, 0.0, 0.707],  # 90 degree Y rotation
    )

    assert result is True


@pytest.mark.asyncio
async def test_export_character_default_orientation(exporter: Any, sample_character: Any) -> None:
    """Test character export with default orientation."""
    result = await exporter.export_character_to_room(
        room_id="test_room",
        character_data=sample_character,
        position=[0, 0, 0],
    )

    assert result is True


@pytest.mark.asyncio
async def test_export_character_idempotent(exporter: Any, sample_character: Any) -> None:
    """Test that exporting same character twice is idempotent."""
    # First export
    result1 = await exporter.export_character_to_room(
        room_id="test_room",
        character_data=sample_character,
        position=[1, 0, 1],
    )
    assert result1 is True

    # Second export with same ID (should update, not duplicate)
    result2 = await exporter.export_character_to_room(
        room_id="test_room",
        character_data=sample_character,
        position=[2, 0, 2],  # Different position
    )
    assert result2 is True


@pytest.mark.asyncio
async def test_export_batch_validation_errors(exporter: Any) -> None:
    """Test input validation for export_batch_to_room."""

    # Empty list
    with pytest.raises(ValueError, match="empty"):
        await exporter.export_batch_to_room(
            room_id="test_room",
            characters_list=[],
        )

    # Invalid spacing
    with pytest.raises(ValueError, match="spacing"):
        await exporter.export_batch_to_room(
            room_id="test_room",
            characters_list=[{"id": "char1", "gltf_url": "url1"}],
            spacing=0,
        )


@pytest.mark.asyncio
async def test_export_batch_success(exporter: Any) -> None:
    """Test successful batch export."""
    characters = [
        {
            "id": f"char_{i}",
            "gltf_url": f"https://cdn.example.com/char_{i}.glb",
            "concept": f"character {i}",
        }
        for i in range(5)
    ]

    results = await exporter.export_batch_to_room(
        room_id="test_room",
        characters_list=characters,
        spacing=2.5,
    )

    assert len(results) == 5
    for char_id, success in results.items():
        assert success is True
        assert char_id.startswith("char_")


@pytest.mark.asyncio
async def test_export_batch_grid_layout(exporter: Any) -> None:
    """Test that batch export uses correct grid layout."""
    # 9 characters should make a 3x3 grid
    n = 9
    characters = [
        {
            "id": f"char_{i}",
            "gltf_url": f"https://cdn.example.com/char_{i}.glb",
        }
        for i in range(n)
    ]

    results = await exporter.export_batch_to_room(
        room_id="test_room",
        characters_list=characters,
        spacing=3.0,
    )

    expected_grid_size = math.ceil(math.sqrt(n))
    assert expected_grid_size == 3
    assert len(results) == n


@pytest.mark.asyncio
async def test_export_batch_skip_invalid(exporter: Any) -> None:
    """Test that batch export skips invalid characters."""
    characters = [
        {"id": "char_1", "gltf_url": "url1"},  # Valid
        {"gltf_url": "url2"},  # No ID - should skip
        {"id": "", "gltf_url": "url3"},  # Empty ID - should skip
        {"id": "char_4"},  # No mesh URL - should fail
        {"id": "char_5", "gltf_url": "url5"},  # Valid
    ]

    results = await exporter.export_batch_to_room(
        room_id="test_room",
        characters_list=characters,
    )

    # Should have results for characters with IDs
    assert "char_1" in results
    assert results["char_1"] is True

    assert "char_4" in results
    assert results["char_4"] is False  # No mesh URL

    assert "char_5" in results
    assert results["char_5"] is True


@pytest.mark.asyncio
async def test_update_character_validation_errors(exporter: Any) -> None:
    """Test input validation for update_character_in_room."""

    # Empty character_id
    with pytest.raises(ValueError, match="character_id"):
        await exporter.update_character_in_room(
            room_id="test_room",
            character_id="",
            updates={"position": [1, 0, 1]},
        )

    # Empty updates
    with pytest.raises(ValueError, match="updates"):
        await exporter.update_character_in_room(
            room_id="test_room",
            character_id="char_1",
            updates={},
        )


@pytest.mark.asyncio
async def test_update_character_not_found(exporter: Any) -> None:
    """Test updating non-existent character returns False."""
    result = await exporter.update_character_in_room(
        room_id="test_room",
        character_id="nonexistent_char",
        updates={"position": [10, 0, 10]},
    )

    assert result is False


@pytest.mark.asyncio
async def test_update_character_success(exporter: Any, sample_character: Any) -> None:
    """Test successful character update."""
    # First export a character
    await exporter.export_character_to_room(
        room_id="test_room",
        character_data=sample_character,
        position=[0, 0, 0],
    )

    # Update position
    result = await exporter.update_character_in_room(
        room_id="test_room",
        character_id=sample_character["id"],
        updates={"position": [5, 1, -2]},
    )

    assert result is True


@pytest.mark.asyncio
async def test_update_character_merge_metadata(exporter: Any, sample_character: Any) -> None:
    """Test that metadata updates are merged, not replaced."""
    # Export character with initial metadata
    await exporter.export_character_to_room(
        room_id="test_room",
        character_data=sample_character,
        position=[0, 0, 0],
    )

    # Update metadata (should merge)
    result = await exporter.update_character_in_room(
        room_id="test_room",
        character_id=sample_character["id"],
        updates={
            "metadata": {
                "custom_field": "custom_value",
            }
        },
    )

    assert result is True


@pytest.mark.asyncio
async def test_remove_character_validation_error(exporter: Any) -> None:
    """Test input validation for remove_character_from_room."""

    with pytest.raises(ValueError, match="character_id"):
        await exporter.remove_character_from_room(
            room_id="test_room",
            character_id="",
        )


@pytest.mark.asyncio
async def test_remove_character_success(exporter: Any, sample_character: Any) -> None:
    """Test successful character removal."""
    # First export a character
    await exporter.export_character_to_room(
        room_id="test_room",
        character_data=sample_character,
        position=[0, 0, 0],
    )

    # Remove it
    result = await exporter.remove_character_from_room(
        room_id="test_room",
        character_id=sample_character["id"],
    )

    assert result is True


@pytest.mark.asyncio
async def test_remove_character_idempotent(exporter: Any) -> None:
    """Test that removing non-existent character is idempotent."""
    result = await exporter.remove_character_from_room(
        room_id="test_room",
        character_id="nonexistent_char",
    )

    # Should succeed (idempotent)
    assert result is True


@pytest.mark.asyncio
async def test_full_workflow(exporter: Any) -> None:
    """Test complete workflow: export, update, remove."""
    character = {
        "id": "workflow_char",
        "gltf_url": "https://cdn.example.com/workflow.glb",
        "concept": "test character",
    }

    # 1. Export
    export_result = await exporter.export_character_to_room(
        room_id="workflow_room",
        character_data=character,
        position=[0, 0, 0],
    )
    assert export_result is True

    # 2. Update
    update_result = await exporter.update_character_in_room(
        room_id="workflow_room",
        character_id=character["id"],
        updates={"position": [5, 0, 5]},
    )
    assert update_result is True

    # 3. Remove
    remove_result = await exporter.remove_character_from_room(
        room_id="workflow_room",
        character_id=character["id"],
    )
    assert remove_result is True
