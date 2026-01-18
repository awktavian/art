from __future__ import annotations
from typing import Any

import pytest

pytestmark = pytest.mark.tier_integration


import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

from kagami.forge.modules.world.world_composer import (
    WorldComposeOptions,
    WorldComposer,
    WorldComposeResult,
)


class FakePhysics:
    def __init__(self):
        self.scene = object()

    async def create_physics_scene(
        self, scene_type: str = "character_studio", **kwargs: Any
    ) -> Any:
        self.scene = object()
        return "scene_fake"

    async def import_world_environment(self, world_dir: str):
        # Report the assets found in dir
        assets = []
        p = Path(world_dir)
        for f in p.glob("*.glb"):
            assets.append(str(f))
        return {"success": True, "assets": assets}

    async def add_character_to_scene(
        self, character_mesh_path: str | None = None, **kwargs: Any
    ) -> Any:
        return "character_1"

    async def simulate_character_motion(self, **kwargs) -> Dict[str, Any]:
        return {"frames": [], "success": True, "motion_data": {}}

    async def export_simulation(self, output_path: str, fmt: str = "usd"):
        out = Path(f"{output_path}.usd")
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_bytes(b"usd")
        return {"success": True, "export_path": str(out)}

    def get_performance_metrics(self):
        return {"device": "cpu"}


@pytest.mark.unit
@pytest.mark.asyncio
async def test_world_composer_manifest_and_export(tmp_path: Path) -> Any:
    # Prepare fake world dir with a glb
    world_dir = tmp_path / "world"
    world_dir.mkdir()
    (world_dir / "env.glb").write_bytes(b"glb")

    # Minimal character data
    character_data = {"metadata": {"export_data": {"glb": str(world_dir / "char.glb")}}}
    (world_dir / "char.glb").write_bytes(b"glb")

    physics = FakePhysics()
    composer = WorldComposer(physics, export_manager=None)
    opts = WorldComposeOptions(duration=0.1, fps=10)

    result = await composer.compose(
        character_data=character_data, world_dir=str(world_dir), options=opts
    )

    assert result.success
    assert result.export_path is not None
    manifest = world_dir / "sessions" / f"{opts.export_basename}.manifest.json"
    assert manifest.exists()
    data = json.loads(manifest.read_text())
    assert data["export_path"] == result.export_path


@pytest.mark.unit
@pytest.mark.asyncio
async def test_world_composer_initialization():
    """Test WorldComposer initialization."""
    composer = WorldComposer(physics=None, export_manager=None)
    assert composer.physics is None
    assert composer.export_manager is None


@pytest.mark.unit
@pytest.mark.asyncio
async def test_world_composer_no_physics_error():
    """Test compose fails without physics engine."""
    composer = WorldComposer(physics=None, export_manager=None)
    character_data = {"metadata": {}}

    with pytest.raises(RuntimeError, match="Physics engine required"):
        await composer.compose(character_data=character_data, world_dir="/tmp/world")


@pytest.mark.unit
@pytest.mark.asyncio
async def test_world_composer_world_import_failure(tmp_path: Path) -> None:
    """Test handling of world import failure."""
    world_dir = tmp_path / "world"
    world_dir.mkdir()

    # Fake physics that fails import
    class FailingPhysics(FakePhysics):
        async def import_world_environment(self, world_dir: str):
            return {"success": False, "error": "Import failed"}

    physics = FailingPhysics()
    composer = WorldComposer(physics, export_manager=None)
    character_data = {"metadata": {"export_data": {"glb": str(world_dir / "char.glb")}}}
    (world_dir / "char.glb").write_bytes(b"glb")

    with pytest.raises(RuntimeError, match="World import failed"):
        await composer.compose(character_data=character_data, world_dir=str(world_dir))


@pytest.mark.unit
@pytest.mark.asyncio
async def test_world_composer_no_character_mesh(tmp_path: Path) -> None:
    """Test handling of missing character mesh."""
    world_dir = tmp_path / "world"
    world_dir.mkdir()
    (world_dir / "env.glb").write_bytes(b"glb")

    physics = FakePhysics()
    composer = WorldComposer(physics, export_manager=None)
    # Character data without mesh path
    character_data = {"metadata": {}}

    with pytest.raises(RuntimeError, match="Character mesh not available"):
        await composer.compose(character_data=character_data, world_dir=str(world_dir))


@pytest.mark.unit
@pytest.mark.asyncio
async def test_world_composer_custom_options(tmp_path: Path) -> None:
    """Test compose with custom options."""
    world_dir = tmp_path / "world"
    world_dir.mkdir()
    (world_dir / "env.glb").write_bytes(b"glb")

    character_data = {"metadata": {"export_data": {"glb": str(world_dir / "char.glb")}}}
    (world_dir / "char.glb").write_bytes(b"glb")

    physics = FakePhysics()
    composer = WorldComposer(physics, export_manager=None)

    # Custom options
    opts = WorldComposeOptions(
        scene_type="physics_test",
        duration=10.0,
        fps=30,
        motion_type="jump",
        export_usd=True,
        export_basename="custom_session",
    )

    result = await composer.compose(
        character_data=character_data, world_dir=str(world_dir), options=opts
    )

    assert result.success
    assert result.session_id == f"session_{world_dir.name}"
    # Check custom basename in manifest
    manifest = world_dir / "sessions" / "custom_session.manifest.json"
    assert manifest.exists()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_world_composer_no_export(tmp_path: Path) -> None:
    """Test compose without USD export."""
    world_dir = tmp_path / "world"
    world_dir.mkdir()
    (world_dir / "env.glb").write_bytes(b"glb")

    character_data = {"metadata": {"export_data": {"glb": str(world_dir / "char.glb")}}}
    (world_dir / "char.glb").write_bytes(b"glb")

    physics = FakePhysics()
    composer = WorldComposer(physics, export_manager=None)

    opts = WorldComposeOptions(export_usd=False)

    result = await composer.compose(
        character_data=character_data, world_dir=str(world_dir), options=opts
    )

    assert result.success
    assert result.export_path is None


@pytest.mark.unit
@pytest.mark.asyncio
async def test_world_composer_extract_rigging_data():
    """Test rigging data extraction from character metadata."""
    composer = WorldComposer(physics=None, export_manager=None)

    # Character with rigging data
    character_data = {
        "metadata": {
            "articulated": {
                "urdf_path": "/path/to/model.urdf",
                "mjcf_path": "/path/to/model.xml",
            }
        }
    }

    rigging = composer._extract_rigging_data(character_data)
    assert rigging is not None
    assert rigging["urdf_path"] == "/path/to/model.urdf"
    assert rigging["mjcf_path"] == "/path/to/model.xml"

    # Character without rigging
    character_data_no_rig = {"metadata": {}}
    rigging = composer._extract_rigging_data(character_data_no_rig)
    assert rigging is None


@pytest.mark.unit
@pytest.mark.asyncio
async def test_world_composer_multiple_assets(tmp_path: Path) -> None:
    """Test compose with multiple world assets."""
    world_dir = tmp_path / "world"
    world_dir.mkdir()

    # Multiple GLB files
    (world_dir / "floor.glb").write_bytes(b"glb")
    (world_dir / "wall.glb").write_bytes(b"glb")
    (world_dir / "ceiling.glb").write_bytes(b"glb")

    character_data = {"metadata": {"export_data": {"glb": str(world_dir / "char.glb")}}}
    (world_dir / "char.glb").write_bytes(b"glb")

    physics = FakePhysics()
    composer = WorldComposer(physics, export_manager=None)

    result = await composer.compose(
        character_data=character_data, world_dir=str(world_dir), options=None
    )

    assert result.success
    # Should have loaded 3 world assets
    assert len(result.world_assets) == 3


@pytest.mark.unit
@pytest.mark.asyncio
async def test_world_composer_export_simulation_failure(tmp_path: Path) -> None:
    """Test handling of export simulation failure."""
    world_dir = tmp_path / "world"
    world_dir.mkdir()
    (world_dir / "env.glb").write_bytes(b"glb")

    character_data = {"metadata": {"export_data": {"glb": str(world_dir / "char.glb")}}}
    (world_dir / "char.glb").write_bytes(b"glb")

    # Physics that fails export
    class FailingExportPhysics(FakePhysics):
        async def export_simulation(self, output_path: str, fmt: str = "usd"):
            return {"success": False, "error": "Export failed"}

    physics = FailingExportPhysics()
    composer = WorldComposer(physics, export_manager=None)

    with pytest.raises(RuntimeError, match="Simulation export failed"):
        await composer.compose(
            character_data=character_data,
            world_dir=str(world_dir),
            options=WorldComposeOptions(export_usd=True),
        )


@pytest.mark.unit
@pytest.mark.asyncio
async def test_world_composer_performance_metrics(tmp_path: Path) -> None:
    """Test performance metrics collection."""
    world_dir = tmp_path / "world"
    world_dir.mkdir()
    (world_dir / "env.glb").write_bytes(b"glb")

    character_data = {"metadata": {"export_data": {"glb": str(world_dir / "char.glb")}}}
    (world_dir / "char.glb").write_bytes(b"glb")

    physics = FakePhysics()
    composer = WorldComposer(physics, export_manager=None)

    result = await composer.compose(
        character_data=character_data, world_dir=str(world_dir), options=None
    )

    assert result.success
    assert "physics" in result.performance
    assert result.performance["physics"]["device"] == "cpu"
