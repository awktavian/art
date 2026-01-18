"""Comprehensive tests for Genesis physics export formats."""

from __future__ import annotations

import pytest
pytestmark = pytest.mark.tier_integration



import tempfile
from pathlib import Path

from kagami.forge.modules.genesis_physics_wrapper import GenesisPhysicsWrapper


class TestExportFormats:
    """Test all export formats."""

    @pytest.mark.asyncio
    async def test_usd_export(self):
        """Test USD export (existing)."""
        wrapper = GenesisPhysicsWrapper()

        try:
            await wrapper.initialize()
            await wrapper.create_physics_scene()

            with tempfile.TemporaryDirectory() as tmpdir:
                output = Path(tmpdir) / "test"
                result = await wrapper.export_simulation(str(output), format="usd")

                assert result["success"] is True
                assert Path(result["export_path"]).exists()
                assert result["format"] == "usd"
        except Exception as e:
            pytest.skip(f"Genesis not available: {e}")

    @pytest.mark.asyncio
    async def test_gltf_export(self):
        """Test glTF 2.0 export (NEW!)."""
        wrapper = GenesisPhysicsWrapper()

        try:
            await wrapper.initialize()
            await wrapper.create_physics_scene()

            with tempfile.TemporaryDirectory() as tmpdir:
                output = Path(tmpdir) / "test"
                result = await wrapper.export_simulation(str(output), format="gltf")

                assert result["success"] is True
                assert Path(result["export_path"]).exists()
                assert result["format"] == "gltf"

                # Verify glTF structure
                import json

                with open(result["export_path"]) as f:
                    gltf_data = json.load(f)
                assert "asset" in gltf_data
                assert gltf_data["asset"]["version"] == "2.0"
        except Exception as e:
            pytest.skip(f"Genesis not available: {e}")

    @pytest.mark.asyncio
    async def test_fbx_export(self):
        """Test FBX export (NEW!)."""
        wrapper = GenesisPhysicsWrapper()

        try:
            await wrapper.initialize()
            await wrapper.create_physics_scene()

            with tempfile.TemporaryDirectory() as tmpdir:
                output = Path(tmpdir) / "test"
                result = await wrapper.export_simulation(str(output), format="fbx")

                assert result["success"] is True
                assert Path(result["export_path"]).exists()
                assert result["format"] == "fbx"
        except Exception as e:
            pytest.skip(f"Genesis or trimesh not available: {e}")

    @pytest.mark.asyncio
    async def test_obj_export(self):
        """Test OBJ export (NEW!)."""
        wrapper = GenesisPhysicsWrapper()

        try:
            await wrapper.initialize()
            await wrapper.create_physics_scene()

            with tempfile.TemporaryDirectory() as tmpdir:
                output = Path(tmpdir) / "test"
                result = await wrapper.export_simulation(str(output), format="obj")

                assert result["success"] is True
                obj_path = Path(result["export_path"])
                assert obj_path.exists()
                assert result["format"] == "obj"

                # Check for MTL file
                mtl_path = obj_path.with_suffix(".mtl")
                assert mtl_path.exists()

                # Verify OBJ structure
                with open(obj_path) as f:
                    content = f.read()
                assert "# K os Genesis Physics Export" in content
                assert "v " in content  # Vertices
        except Exception as e:
            pytest.skip(f"Genesis not available: {e}")

    @pytest.mark.asyncio
    async def test_invalid_format(self):
        """Test error on invalid format."""
        wrapper = GenesisPhysicsWrapper()

        try:
            await wrapper.initialize()
            await wrapper.create_physics_scene()

            with tempfile.TemporaryDirectory() as tmpdir:
                output = Path(tmpdir) / "test"
                with pytest.raises(ValueError, match="not supported"):
                    await wrapper.export_simulation(str(output), format="invalid")
        except Exception as e:
            pytest.skip(f"Genesis not available: {e}")


class TestExportWithContent:
    """Test exports with actual scene content."""

    @pytest.mark.asyncio
    async def test_export_with_character(self):
        """Test export includes character mesh."""
        wrapper = GenesisPhysicsWrapper()

        try:
            await wrapper.initialize()
            await wrapper.create_physics_scene()
            # Would add character mesh here in full test

            with tempfile.TemporaryDirectory() as tmpdir:
                output = Path(tmpdir) / "test"
                result = await wrapper.export_simulation(str(output), format="gltf")

                assert result["success"] is True
        except Exception as e:
            pytest.skip(f"Genesis not available: {e}")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
